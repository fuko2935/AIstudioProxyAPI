"""
API yardımcı fonksiyonları modülü.
SSE üretimi, akış işleme, token istatistikleri ve istek doğrulama gibi araçları içerir.
"""

import asyncio
import json
import time
import datetime
from typing import Any, Dict, List, Optional, AsyncGenerator
from asyncio import Queue
from models import Message
import re
import base64
import requests
import os
import hashlib


# --- SSE üretim fonksiyonları ---
def generate_sse_chunk(delta: str, req_id: str, model: str) -> str:
    """SSE veri bloğu oluşturur"""
    chunk_data = {
        "id": f"chatcmpl-{req_id}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]
    }
    return f"data: {json.dumps(chunk_data)}\n\n"


def generate_sse_stop_chunk(req_id: str, model: str, reason: str = "stop", usage: dict = None) -> str:
    """SSE durdurma bloğu oluşturur"""
    stop_chunk_data = {
        "id": f"chatcmpl-{req_id}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": reason}]
    }
    
    # usage bilgisi verildiyse ekle
    if usage:
        stop_chunk_data["usage"] = usage
    
    return f"data: {json.dumps(stop_chunk_data)}\n\ndata: [DONE]\n\n"


def generate_sse_error_chunk(message: str, req_id: str, error_type: str = "server_error") -> str:
    """SSE hata bloğu oluşturur"""
    error_chunk = {"error": {"message": message, "type": error_type, "param": None, "code": req_id}}
    return f"data: {json.dumps(error_chunk)}\n\n"


# --- Akış işleme araçları ---
async def use_stream_response(req_id: str) -> AsyncGenerator[Any, None]:
    """Sunucunun global kuyruğundan veri çekerek akış yanıtı kullanır"""
    from server import STREAM_QUEUE, logger
    import queue
    
    if STREAM_QUEUE is None:
        logger.warning(f"[{req_id}] STREAM_QUEUE boş, akış yanıtı kullanılamıyor")
        return
    
    logger.info(f"[{req_id}] Akış yanıtı kullanılmaya başlandı")
    
    empty_count = 0
    max_empty_retries = 300  # 30 saniyelik zaman aşımı
    data_received = False
    
    try:
        while True:
            try:
                # Kuyruktan veri al
                data = STREAM_QUEUE.get_nowait()
                if data is None:  # Bitiş işareti
                    logger.info(f"[{req_id}] Akış bitiş sinyali alındı")
                    break
                
                # Boş sayaç sıfırla
                empty_count = 0
                data_received = True
                logger.debug(f"[{req_id}] Akış verisi alındı: {type(data)} - {str(data)[:200]}...")
                
                # JSON string biçiminde bitiş işareti var mı kontrol et
                if isinstance(data, str):
                    try:
                        parsed_data = json.loads(data)
                        if parsed_data.get("done") is True:
                            logger.info(f"[{req_id}] JSON formatında tamamlanma işareti alındı")
                            yield parsed_data
                            break
                        else:
                            yield parsed_data
                    except json.JSONDecodeError:
                        # JSON değilse doğrudan string döndür
                        logger.debug(f"[{req_id}] JSON olmayan string veri döndürülüyor")
                        yield data
                else:
                    # Veriyi doğrudan döndür
                    yield data
                    
                    # Sözlük tipinde bitiş işareti olup olmadığını denetle
                    if isinstance(data, dict) and data.get("done") is True:
                        logger.info(f"[{req_id}] Sözlük formatında tamamlanma işareti alındı")
                        break
                
            except (queue.Empty, asyncio.QueueEmpty):
                empty_count += 1
                if empty_count % 50 == 0:  # Her 5 saniyede bekleme durumunu kaydet
                    logger.info(f"[{req_id}] Akış verisi bekleniyor... ({empty_count}/{max_empty_retries})")
                
                if empty_count >= max_empty_retries:
                    if not data_received:
                        logger.error(f"[{req_id}] Akış kuyruğunda veri alınamadı; yardımcı akış başlamamış olabilir")
                    else:
                        logger.warning(f"[{req_id}] Akış kuyruğunda boş okuma sayısı limite ulaştı ({max_empty_retries}); okuma sonlandırılıyor")
                    
                    # Basitçe çıkmak yerine zaman aşımı tamamlanma sinyali gönder
                    yield {"done": True, "reason": "internal_timeout", "body": "", "function": []}
                    return
                    
                await asyncio.sleep(0.1)  # 100ms bekle
                continue
                
    except Exception as e:
        logger.error(f"[{req_id}] Akış yanıtı kullanılırken hata: {e}")
        raise
    finally:
        logger.info(f"[{req_id}] Akış yanıtı tamamlandı; veri alındı mı: {data_received}")


async def clear_stream_queue():
    """Akış kuyruğunu temizler (orijinal davranış ile uyumlu)"""
    from server import STREAM_QUEUE, logger
    import queue

    if STREAM_QUEUE is None:
        logger.info("Akış kuyruğu başlatılmamış veya devre dışı; temizleme atlandı.")
        return

    while True:
        try:
            data_chunk = await asyncio.to_thread(STREAM_QUEUE.get_nowait)
            # logger.info(f"Akış kuyruğundaki veri temizlendi: {data_chunk}")
        except queue.Empty:
            logger.info("Akış kuyruğu boş (queue.Empty yakalandı).")
            break
        except Exception as e:
            logger.error(f"Akış kuyruğu temizlenirken beklenmeyen hata: {e}", exc_info=True)
            break
    logger.info("Akış kuyruğu temizliği tamamlandı.")


# --- Helper response generator ---
async def use_helper_get_response(helper_endpoint: str, helper_sapisid: str) -> AsyncGenerator[str, None]:
    """Helper servisi üzerinden yanıt sağlayan üretici"""
    from server import logger
    import aiohttp

    logger.info(f"Helper uç noktası kullanılmaya çalışılıyor: {helper_endpoint}")

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'Content-Type': 'application/json',
                'Cookie': f'SAPISID={helper_sapisid}' if helper_sapisid else ''
            }
            
            async with session.get(helper_endpoint, headers=headers) as response:
                if response.status == 200:
                    async for chunk in response.content.iter_chunked(1024):
                        if chunk:
                            yield chunk.decode('utf-8', errors='ignore')
                else:
                    logger.error(f"Helper uç noktası hata durumu döndürdü: {response.status}")
                    
    except Exception as e:
        logger.error(f"Helper uç noktası kullanılırken hata: {e}")


# --- İstek doğrulama fonksiyonları ---
def validate_chat_request(messages: List[Message], req_id: str) -> Dict[str, Optional[str]]:
    """Sohbet isteğini doğrular"""
    from server import logger
    
    if not messages:
        raise ValueError(f"[{req_id}] Geçersiz istek: 'messages' dizisi eksik veya boş.")

    if not any(msg.role != 'system' for msg in messages):
        raise ValueError(f"[{req_id}] Geçersiz istek: Tüm mesajlar sistem rolüne sahip. En az bir kullanıcı veya asistan mesajı gerekli.")
    
    # Doğrulama sonucunu döndür
    return {
        "error": None,
        "warning": None
    }


def extract_base64_to_local(base64_data: str) -> str:
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'upload_images')
    match = re.match(r"data:image/(\w+);base64,(.*)", base64_data)
    if not match:
        print("Hata: Base64 veri formatı geçersiz.")
        return None

    image_type = match.group(1)  # örneğin "png", "jpeg"
    encoded_image_data = match.group(2)

    try:
        # Base64 string'ini çöz
        decoded_image_data = base64.b64decode(encoded_image_data)
    except base64.binascii.Error as e:
        print(f"Hata: Base64 çözümlenemedi - {e}")
        return None

    # Görsel verisinin MD5 değerini hesapla
    md5_hash = hashlib.md5(decoded_image_data).hexdigest()

    # Dosya uzantısını ve tam yolu belirle
    file_extension = f".{image_type}"
    output_filepath = os.path.join(output_dir, f"{md5_hash}{file_extension}")

    # Çıkış klasörünün var olduğundan emin ol
    os.makedirs(output_dir, exist_ok=True)

    if os.path.exists(output_filepath):
        print(f"Dosya zaten mevcut, kaydedilmiyor: {output_filepath}")
        return output_filepath

    # Görseli dosyaya kaydet
    try:
        with open(output_filepath, "wb") as f:
            f.write(decoded_image_data)
        print(f"Görsel başarıyla kaydedildi: {output_filepath}")
        return output_filepath
    except IOError as e:
        print(f"Hata: Dosya kaydedilemedi - {e}")
        return None


# --- İpucu hazırlama fonksiyonları ---
def prepare_combined_prompt(messages: List[Message], req_id: str) -> str:
    """Birleşik istemi hazırlar"""
    from server import logger
    
    logger.info(f"[{req_id}] (İstem Hazırlama) {len(messages)} mesajdan birleşik istem hazırlanıyor (geçmiş dahil).")
    
    combined_parts = []
    system_prompt_content: Optional[str] = None
    processed_system_message_indices = set()
    images_list = []  # image_list'i döngü dışında başlat

    # Sistem mesajlarını işle
    for i, msg in enumerate(messages):
        if msg.role == 'system':
            content = msg.content
            if isinstance(content, str) and content.strip():
                system_prompt_content = content.strip()
                processed_system_message_indices.add(i)
                logger.info(f"[{req_id}] (İstem Hazırlama) İndeks {i} konumunda sistem yönergesi bulundu: '{system_prompt_content[:80]}...'")
                system_instr_prefix = "Sistem talimatı:\n"
                combined_parts.append(f"{system_instr_prefix}{system_prompt_content}")
            else:
                logger.info(f"[{req_id}] (İstem Hazırlama) İndeks {i} konumundaki boş veya geçersiz sistem mesajı atlandı.")
                processed_system_message_indices.add(i)
            break
    
    role_map_ui = {"user": "", "assistant": "", "system": "", "tool": ""}
    turn_separator = "\n---\n"
    
    # Diğer mesajları işle
    for i, msg in enumerate(messages):
        if i in processed_system_message_indices:
            continue
        
        if msg.role == 'system':
            logger.info(f"[{req_id}] (İstem Hazırlama) İndeks {i} konumundaki ek sistem mesajı atlandı.")
            continue
        
        if combined_parts:
            combined_parts.append(turn_separator)
        
        role = msg.role or 'unknown'
        role_label = role_map_ui.get(role, "")
        current_turn_parts = []
        if role_label:
            current_turn_parts.append(f"{role_label}:\n")
        
        content = msg.content or ''
        content_str = ""
        
        if isinstance(content, str):
            content_str = content.strip()
        elif isinstance(content, list):
            # Çok modlu içeriği işle
            text_parts = []
            for item in content:
                if hasattr(item, 'type') and item.type == 'text':
                    text_parts.append(item.text or '')
                elif isinstance(item, dict) and item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
                elif hasattr(item, 'type') and item.type == 'image_url':
                    image_url_value = item.image_url.url
                    if image_url_value.startswith("data:image/"):
                        try:
                            # Base64 string'ini ayıkla
                            image_full_path = extract_base64_to_local(image_url_value)
                            images_list.append(image_full_path)
                        except (ValueError, requests.exceptions.RequestException, Exception) as e:
                            print(f"Base64 görsel işlenip yüklenemedi: {e}")
                else:
                    logger.warning(f"[{req_id}] (İstem Hazırlama) Uyarı: İndeks {i} içindeki bilinmeyen içerik öğesi atlandı")
            content_str = "\n".join(text_parts).strip()
        else:
            logger.warning(f"[{req_id}] (İstem Hazırlama) Uyarı: Rol {role} için beklenmeyen içerik türü ({type(content)}) veya None bulundu (indeks {i}).")
            content_str = str(content or "").strip()
        
        if content_str:
            current_turn_parts.append(content_str)
        
        # Araç çağrılarını işle
        tool_calls = msg.tool_calls
        if role == 'assistant' and tool_calls:
            if content_str:
                current_turn_parts.append("\n")
            
            tool_call_visualizations = []
            for tool_call in tool_calls:
                if hasattr(tool_call, 'type') and tool_call.type == 'function':
                    function_call = tool_call.function
                    func_name = function_call.name if function_call else None
                    func_args_str = function_call.arguments if function_call else None
                    
                    try:
                        parsed_args = json.loads(func_args_str if func_args_str else '{}')
                        formatted_args = json.dumps(parsed_args, indent=2, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        formatted_args = func_args_str if func_args_str is not None else "{}"
                    
                    tool_call_visualizations.append(
                        f"Fonksiyon çağrısı isteği: {func_name}\nParametreler:\n{formatted_args}"
                    )
            
            if tool_call_visualizations:
                current_turn_parts.append("\n".join(tool_call_visualizations))
        
        if current_turn_parts:
            combined_parts.append("".join(current_turn_parts))
        else:
            if not combined_parts:
                logger.info(f"[{req_id}] (İstem Hazırlama) Rol {role} için indeks {i} konumundaki boş mesaj (araç çağrısı yok) atlandı.")
            else:
                logger.debug(f"[{req_id}] (İstem Hazırlama) Rol {role} için indeks {i} konumunda eklenebilir içerik bulunamadı.")
    
    final_prompt = "".join(combined_parts)
    if final_prompt:
        final_prompt += "\n"
    
    preview_text = final_prompt[:300].replace('\n', '\\n')
    logger.info(f"[{req_id}] (İstem Hazırlama) Birleşik istem uzunluğu: {len(final_prompt)}. Önizleme: '{preview_text}...'")
    
    return final_prompt,images_list


def estimate_tokens(text: str) -> int:
    """
    Metindeki tahmini token sayısını hesaplar.
    Basit karakter sayımı kuralları:
    - İngilizce: yaklaşık 4 karakter = 1 token
    - Çince: yaklaşık 1.5 karakter = 1 token
    - Karma metin: ağırlıklı ortalama kullanılır
    """
    if not text:
        return 0
    
    # Çince karakterlerin (noktalama dahil) sayısını hesapla
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff' or '\u3000' <= char <= '\u303f' or '\uff00' <= char <= '\uffef')
    
    # Diğer karakterleri say
    non_chinese_chars = len(text) - chinese_chars
    
    # Token tahmini
    chinese_tokens = chinese_chars / 1.5  # Çince ~1.5 karakter/token
    english_tokens = non_chinese_chars / 4.0  # İngilizce ~4 karakter/token
    
    return max(1, int(chinese_tokens + english_tokens))


def calculate_usage_stats(messages: List[dict], response_content: str, reasoning_content: str = None) -> dict:
    """
    Token kullanım istatistiklerini hesaplar.
    
    Args:
        messages: İstem mesajları listesi
        response_content: Yanıt metni
        reasoning_content: Opsiyonel çıkarım içeriği
    
    Returns:
        Token kullanım bilgilerini içeren sözlük
    """
    # Girdi token sayısını hesapla (prompt tokens)
    prompt_text = ""
    for message in messages:
        role = message.get("role", "")
        content = message.get("content", "")
        prompt_text += f"{role}: {content}\n"
    
    prompt_tokens = estimate_tokens(prompt_text)
    
    # Çıktı token sayısını hesapla (completion tokens)
    completion_text = response_content or ""
    if reasoning_content:
        completion_text += reasoning_content
    
    completion_tokens = estimate_tokens(completion_text)
    
    # Toplam token sayısı
    total_tokens = prompt_tokens + completion_tokens
    
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens
    } 


def generate_sse_stop_chunk_with_usage(req_id: str, model: str, usage_stats: dict, reason: str = "stop") -> str:
    """Kullanım istatistiklerini içeren SSE durdurma bloğu oluşturur"""
    return generate_sse_stop_chunk(req_id, model, reason, usage_stats) 
