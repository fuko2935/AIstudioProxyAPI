"""
İstek işlemcisi modülü.
Çekirdek istek işleme mantığını içerir.
"""

import asyncio
import json
import os
import random
import time
from typing import Optional, Tuple, Callable, AsyncGenerator
from asyncio import Event, Future

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from playwright.async_api import Page as AsyncPage, Locator, Error as PlaywrightAsyncError, expect as expect_async

# --- Yapılandırma modülünü içe aktar ---
from config import *

# --- models modülünü içe aktar ---
from models import ChatCompletionRequest, ClientDisconnectedError

# --- browser_utils modülünü içe aktar ---
from browser_utils import (
    switch_ai_studio_model,
    save_error_snapshot
)

# --- api_utils modülünü içe aktar ---
from .utils import (
    validate_chat_request,
    prepare_combined_prompt,
    generate_sse_chunk,
    generate_sse_stop_chunk,
    use_stream_response,
    calculate_usage_stats
)
from browser_utils.page_controller import PageController


async def _initialize_request_context(req_id: str, request: ChatCompletionRequest) -> dict:
    """İstek bağlamını hazırlar"""
    from server import (
        logger, page_instance, is_page_ready, parsed_model_list,
        current_ai_studio_model_id, model_switching_lock, page_params_cache,
        params_cache_lock
    )
    
    logger.info(f"[{req_id}] İstek işlenmeye başlıyor...")
    logger.info(f"[{req_id}]   Parametreler - Model: {request.model}, Stream: {request.stream}")
    
    context = {
        'logger': logger,
        'page': page_instance,
        'is_page_ready': is_page_ready,
        'parsed_model_list': parsed_model_list,
        'current_ai_studio_model_id': current_ai_studio_model_id,
        'model_switching_lock': model_switching_lock,
        'page_params_cache': page_params_cache,
        'params_cache_lock': params_cache_lock,
        'is_streaming': request.stream,
        'model_actually_switched': False,
        'requested_model': request.model,
        'model_id_to_use': None,
        'needs_model_switching': False
    }
    
    return context


async def _analyze_model_requirements(req_id: str, context: dict, request: ChatCompletionRequest) -> dict:
    """Model gereksinimini analiz eder ve değişim gerekip gerekmediğini belirler"""
    logger = context['logger']
    current_ai_studio_model_id = context['current_ai_studio_model_id']
    parsed_model_list = context['parsed_model_list']
    requested_model = request.model
    
    if requested_model and requested_model != MODEL_NAME:
        requested_model_id = requested_model.split('/')[-1]
        logger.info(f"[{req_id}] İstek, {requested_model_id} modelinin kullanılmasını talep ediyor")
        
        if parsed_model_list:
            valid_model_ids = [m.get("id") for m in parsed_model_list]
            if requested_model_id not in valid_model_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"[{req_id}] Invalid model '{requested_model_id}'. Available models: {', '.join(valid_model_ids)}"
                )
        
        context['model_id_to_use'] = requested_model_id
        if current_ai_studio_model_id != requested_model_id:
            context['needs_model_switching'] = True
            logger.info(f"[{req_id}] Model değişimi gerekli: mevcut={current_ai_studio_model_id} -> hedef={requested_model_id}")
    
    return context


async def _test_client_connection(req_id: str, http_request: Request) -> bool:
    """Küçük bir test paketi göndererek istemci bağlantısını doğrular"""
    try:
        # Küçük bir test paketi göndermeyi dene
        test_chunk = "data: {\"type\":\"ping\"}\n\n"

        # Alt düzey yanıt nesnesini al
        if hasattr(http_request, '_receive'):
            # Alım kanalının aktif olup olmadığını kontrol et
            try:
                # Engellemeden bağlantı kopması mesajı olup olmadığını dene
                import asyncio
                receive_task = asyncio.create_task(http_request._receive())
                done, pending = await asyncio.wait([receive_task], timeout=0.01)

                if done:
                    message = receive_task.result()
                    if message.get("type") == "http.disconnect":
                        return False
                else:
                    # Tamamlanmayan görevi iptal et
                    receive_task.cancel()
                    try:
                        await receive_task
                    except asyncio.CancelledError:
                        pass

            except Exception:
                # Denetim sırasında hata oluşursa bağlantı sorunlu olabilir
                return False

        # Tüm kontroller geçerse bağlantı sağlıklı kabul edilir
        return True

    except Exception as e:
        # Herhangi bir istisna bağlantının koptuğu anlamına gelir
        return False

async def _setup_disconnect_monitoring(req_id: str, http_request: Request, result_future: Future) -> Tuple[Event, asyncio.Task, Callable]:
    """İstemci bağlantı kopmalarını takip eder"""
    from server import logger

    client_disconnected_event = Event()

    async def check_disconnect_periodically():
        while not client_disconnected_event.is_set():
            try:
                # Proaktif kontrol yöntemi
                is_connected = await _test_client_connection(req_id, http_request)
                if not is_connected:
                    logger.info(f"[{req_id}] Proaktif kontrol istemci bağlantısının koptuğunu gösterdi.")
                    client_disconnected_event.set()
                    if not result_future.done():
                        result_future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] İstemci isteği kapattı"))
                    break

                # Yedek kontrol: mevcut is_disconnected yöntemini kullan
                if await http_request.is_disconnected():
                    logger.info(f"[{req_id}] Yedek kontrol istemci bağlantısının koptuğunu gösterdi.")
                    client_disconnected_event.set()
                    if not result_future.done():
                        result_future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] İstemci isteği kapattı"))
                    break

                await asyncio.sleep(0.3)  # Daha sık kontrol aralığı (0.5 sn'den 0.3 sn'ye)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{req_id}] (Disco Check Task) hata: {e}")
                client_disconnected_event.set()
                if not result_future.done():
                    result_future.set_exception(HTTPException(status_code=500, detail=f"[{req_id}] Internal disconnect checker error: {e}"))
                break

    disconnect_check_task = asyncio.create_task(check_disconnect_periodically())

    def check_client_disconnected(stage: str = ""):
        if client_disconnected_event.is_set():
            logger.info(f"[{req_id}] '{stage}' aşamasında istemci bağlantısı koptu.")
            raise ClientDisconnectedError(f"[{req_id}] Client disconnected at stage: {stage}")
        return False

    return client_disconnected_event, disconnect_check_task, check_client_disconnected


async def _validate_page_status(req_id: str, context: dict, check_client_disconnected: Callable) -> None:
    """Sayfanın hazır olup olmadığını doğrular"""
    page = context['page']
    is_page_ready = context['is_page_ready']
    
    if not page or page.is_closed() or not is_page_ready:
        raise HTTPException(status_code=503, detail=f"[{req_id}] AI Studio sayfası bulunamadı ya da hazır değil.", headers={"Retry-After": "30"})
    
    check_client_disconnected("Initial Page Check")


async def _handle_model_switching(req_id: str, context: dict, check_client_disconnected: Callable) -> dict:
    """Model değiştirme mantığını yürütür"""
    if not context['needs_model_switching']:
        return context
    
    logger = context['logger']
    page = context['page']
    model_switching_lock = context['model_switching_lock']
    model_id_to_use = context['model_id_to_use']
    
    import server
    
    async with model_switching_lock:
        if server.current_ai_studio_model_id != model_id_to_use:
            logger.info(f"[{req_id}] Model değişimi hazırlanıyor: {server.current_ai_studio_model_id} -> {model_id_to_use}")
            switch_success = await switch_ai_studio_model(page, model_id_to_use, req_id)
            if switch_success:
                server.current_ai_studio_model_id = model_id_to_use
                context['model_actually_switched'] = True
                context['current_ai_studio_model_id'] = model_id_to_use
                logger.info(f"[{req_id}] ✅ Model başarıyla değiştirildi: {server.current_ai_studio_model_id}")
            else:
                await _handle_model_switch_failure(req_id, page, model_id_to_use, server.current_ai_studio_model_id, logger)
    
    return context


async def _handle_model_switch_failure(req_id: str, page: AsyncPage, model_id_to_use: str, model_before_switch: str, logger) -> None:
    """Model değişiminin başarısız olduğu durumu ele alır"""
    import server
    
    logger.warning(f"[{req_id}] ❌ Model {model_id_to_use} değerine geçirilemedi.")
    # Global durumu eski haline döndür
    server.current_ai_studio_model_id = model_before_switch
    
    raise HTTPException(
        status_code=422,
        detail=f"[{req_id}] '{model_id_to_use}' modeline geçilemedi. Lütfen modelin erişilebilir olduğundan emin olun."
    )


async def _handle_parameter_cache(req_id: str, context: dict) -> None:
    """Parametre önbelleğini yönetir"""
    logger = context['logger']
    params_cache_lock = context['params_cache_lock']
    page_params_cache = context['page_params_cache']
    current_ai_studio_model_id = context['current_ai_studio_model_id']
    model_actually_switched = context['model_actually_switched']
    
    async with params_cache_lock:
        cached_model_for_params = page_params_cache.get("last_known_model_id_for_params")
        
        if model_actually_switched or (current_ai_studio_model_id != cached_model_for_params):
            logger.info(f"[{req_id}] Model değişti; parametre önbelleği temizleniyor.")
            page_params_cache.clear()
            page_params_cache["last_known_model_id_for_params"] = current_ai_studio_model_id


async def _prepare_and_validate_request(req_id: str, request: ChatCompletionRequest, check_client_disconnected: Callable) -> str:
    """İsteği hazırlar ve doğrular"""
    try:
        validate_chat_request(request.messages, req_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"[{req_id}] Geçersiz istek: {e}")
    
    prepared_prompt = prepare_combined_prompt(request.messages, req_id)
    check_client_disconnected("After Prompt Prep")
    
    return prepared_prompt

async def _handle_response_processing(req_id: str, request: ChatCompletionRequest, page: AsyncPage,
                                    context: dict, result_future: Future,
                                    submit_button_locator: Locator, check_client_disconnected: Callable) -> Optional[Tuple[Event, Locator, Callable]]:
    """Yanıt üretim sürecini yönetir"""
    from server import logger
    
    is_streaming = request.stream
    current_ai_studio_model_id = context.get('current_ai_studio_model_id')
    
    # Yardımcı akış kullanılacak mı kontrol et
    stream_port = os.environ.get('STREAM_PORT')
    use_stream = stream_port != '0'
    
    if use_stream:
        return await _handle_auxiliary_stream_response(req_id, request, context, result_future, submit_button_locator, check_client_disconnected)
    else:
        return await _handle_playwright_response(req_id, request, page, context, result_future, submit_button_locator, check_client_disconnected)


async def _handle_auxiliary_stream_response(req_id: str, request: ChatCompletionRequest, context: dict, 
                                          result_future: Future, submit_button_locator: Locator, 
                                          check_client_disconnected: Callable) -> Optional[Tuple[Event, Locator, Callable]]:
    """Yanıtı yardımcı akış aracılığıyla işler"""
    from server import logger
    
    is_streaming = request.stream
    current_ai_studio_model_id = context.get('current_ai_studio_model_id')
    
    def generate_random_string(length):
        charset = "abcdefghijklmnopqrstuvwxyz0123456789"
        return ''.join(random.choice(charset) for _ in range(length))

    if is_streaming:
        try:
            completion_event = Event()
            
            async def create_stream_generator_from_helper(event_to_set: Event) -> AsyncGenerator[str, None]:
                last_reason_pos = 0
                last_body_pos = 0
                model_name_for_stream = current_ai_studio_model_id or MODEL_NAME
                chat_completion_id = f"{CHAT_COMPLETION_ID_PREFIX}{req_id}-{int(time.time())}-{random.randint(100, 999)}"
                created_timestamp = int(time.time())

                # Kullanım istatistiğini hesaplamak için tam içeriği biriktir
                full_reasoning_content = ""
                full_body_content = ""

                # Veri alım durum bayrağı
                data_receiving = False

                try:
                    async for raw_data in use_stream_response(req_id):
                        # Veri alınmaya başlandığını işaretle
                        data_receiving = True

                        # İstemci bağlantısının kopup kopmadığını kontrol et
                        try:
                            check_client_disconnected(f"Streaming döngüsü ({req_id})")
                        except ClientDisconnectedError:
                            logger.info(f"[{req_id}] İstemci bağlantısı koptu, akış sonlandırılıyor")
                            # Veri alınırken bağlantı koparsa done sinyalini hemen tetikle
                            if data_receiving and not event_to_set.is_set():
                                logger.info(f"[{req_id}] Veri alınırken istemci bağlantısı koptu; done sinyali gönderiliyor")
                                event_to_set.set()
                            break
                        
                        # emin olmak data Sozluk turu
                        if isinstance(raw_data, str):
                            try:
                                data = json.loads(raw_data)
                            except json.JSONDecodeError:
                                logger.warning(f"[{req_id}] Akış verisi JSON olarak çözülemedi: {raw_data}")
                                continue
                        elif isinstance(raw_data, dict):
                            data = raw_data
                        else:
                            logger.warning(f"[{req_id}] Bilinmeyen akış veri türü: {type(raw_data)}")
                            continue

                        # Gerekli anahtarların mevcut olduğundan emin ol
                        if not isinstance(data, dict):
                            logger.warning(f"[{req_id}] Veri sözlük biçiminde değil: {data}")
                            continue
                        
                        reason = data.get("reason", "")
                        body = data.get("body", "")
                        done = data.get("done", False)
                        function = data.get("function", [])
                        
                        # Tam içerik kayıtlarını güncelle
                        if reason:
                            full_reasoning_content = reason
                        if body:
                            full_body_content = body
                        
                        # Reasoning içeriklerini işle
                        if len(reason) > last_reason_pos:
                            output = {
                                "id": chat_completion_id,
                                "object": "chat.completion.chunk",
                                "model": model_name_for_stream,
                                "created": created_timestamp,
                                "choices":[{
                                    "index": 0,
                                    "delta":{
                                        "role": "assistant",
                                        "content": None,
                                        "reasoning_content": reason[last_reason_pos:],
                                    },
                                    "finish_reason": None,
                                    "native_finish_reason": None,
                                }]
                            }
                            last_reason_pos = len(reason)
                            yield f"data: {json.dumps(output, ensure_ascii=False, separators=(',', ':'))}\n\n"
                        
                        # Asıl içerik bloğunu işle
                        if len(body) > last_body_pos:
                            finish_reason_val = None
                            if done:
                                finish_reason_val = "stop"
                            
                            delta_content = {"role": "assistant", "content": body[last_body_pos:]}
                            choice_item = {
                                "index": 0,
                                "delta": delta_content,
                                "finish_reason": finish_reason_val,
                                "native_finish_reason": finish_reason_val,
                            }

                            if done and function and len(function) > 0:
                                tool_calls_list = []
                                for func_idx, function_call_data in enumerate(function):
                                    tool_calls_list.append({
                                        "id": f"call_{generate_random_string(24)}",
                                        "index": func_idx,
                                        "type": "function",
                                        "function": {
                                            "name": function_call_data["name"],
                                            "arguments": json.dumps(function_call_data["params"]),
                                        },
                                    })
                                delta_content["tool_calls"] = tool_calls_list
                                choice_item["finish_reason"] = "tool_calls"
                                choice_item["native_finish_reason"] = "tool_calls"
                                delta_content["content"] = None

                            output = {
                                "id": chat_completion_id,
                                "object": "chat.completion.chunk",
                                "model": model_name_for_stream,
                                "created": created_timestamp,
                                "choices": [choice_item]
                            }
                            last_body_pos = len(body)
                            yield f"data: {json.dumps(output, ensure_ascii=False, separators=(',', ':'))}\n\n"
                        
                        # yalnzca tutamakdone=TrueAma yeni icerik yok（Yalnzca islev cagrs veya saf son）
                        elif done:
                            # Bir islev cagrs varsa ama yeni bir cagr yoksabodyicerik
                            if function and len(function) > 0:
                                delta_content = {"role": "assistant", "content": None}
                                tool_calls_list = []
                                for func_idx, function_call_data in enumerate(function):
                                    tool_calls_list.append({
                                        "id": f"call_{generate_random_string(24)}",
                                        "index": func_idx,
                                        "type": "function",
                                        "function": {
                                            "name": function_call_data["name"],
                                            "arguments": json.dumps(function_call_data["params"]),
                                        },
                                    })
                                delta_content["tool_calls"] = tool_calls_list
                                choice_item = {
                                    "index": 0,
                                    "delta": delta_content,
                                    "finish_reason": "tool_calls",
                                    "native_finish_reason": "tool_calls",
                                }
                            else:
                                # Saf son: yeni içerik veya fonksiyon çağrısı yok
                                choice_item = {
                                    "index": 0,
                                    "delta": {"role": "assistant"},
                                    "finish_reason": "stop",
                                    "native_finish_reason": "stop",
                                }

                            output = {
                                "id": chat_completion_id,
                                "object": "chat.completion.chunk",
                                "model": model_name_for_stream,
                                "created": created_timestamp,
                                "choices": [choice_item]
                            }
                            yield f"data: {json.dumps(output, ensure_ascii=False, separators=(',', ':'))}\n\n"
                
                except ClientDisconnectedError:
                    logger.info(f"[{req_id}] Aks jeneratorunde tespit edilen istemci baglants")
                    # Musterinin baglants kesildiginde hemen ayarlayndoneSinyal
                    if data_receiving and not event_to_set.is_set():
                        logger.info(f"[{req_id}] Istemci baglantsnn kesilmesi istisnasnn islenmesi srasnda hemen ayarlayndoneSinyal")
                        event_to_set.set()
                except Exception as e:
                    logger.error(f"[{req_id}] Aks jenerator isleme srasnda bir hata olustu: {e}", exc_info=True)
                    # Istemciye hata mesaj gonder
                    try:
                        error_chunk = {
                            "id": chat_completion_id,
                            "object": "chat.completion.chunk",
                            "model": model_name_for_stream,
                            "created": created_timestamp,
                            "choices": [{
                                "index": 0,
                                "delta": {"role": "assistant", "content": f"\n\n[hata: {str(e)}]"},
                                "finish_reason": "stop",
                                "native_finish_reason": "stop",
                            }]
                        }
                        yield f"data: {json.dumps(error_chunk, ensure_ascii=False, separators=(',', ':'))}\n\n"
                    except Exception:
                        pass  # Hata mesajı gönderilemezse sürecin son kısmına devam et
                finally:
                    # Kullanım istatistiklerini hesapla
                    try:
                        usage_stats = calculate_usage_stats(
                            [msg.model_dump() for msg in request.messages],
                            full_body_content,
                            full_reasoning_content
                        )
                        logger.info(f"[{req_id}] Hesaplanan token kullanım istatistikleri: {usage_stats}")
                        
                        # Bant gonderusageFinalchunk
                        final_chunk = {
                            "id": chat_completion_id,
                            "object": "chat.completion.chunk",
                            "model": model_name_for_stream,
                            "created": created_timestamp,
                            "choices": [{
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop",
                                "native_finish_reason": "stop"
                            }],
                            "usage": usage_stats
                        }
                        yield f"data: {json.dumps(final_chunk, ensure_ascii=False, separators=(',', ':'))}\n\n"
                        logger.info(f"[{req_id}] Kullanım istatistiklerini içeren son parça gönderildi")
                    
                    except Exception as usage_err:
                        logger.error(f"[{req_id}] Kullanım istatistikleri hesaplanırken veya gönderilirken hata oluştu: {usage_err}")
                    
                    # [DONE] işaretinin her durumda gönderildiğinden emin ol
                    try:
                        logger.info(f"[{req_id}] Akış üreticisi tamamlandı, [DONE] işareti gönderiliyor")
                        yield "data: [DONE]\n\n"
                    except Exception as done_err:
                        logger.error(f"[{req_id}] [DONE] işareti gönderilirken hata oluştu: {done_err}")
                    
                    # Olayın mutlaka işaretlenmesini sağla
                    if not event_to_set.is_set():
                        event_to_set.set()
                        logger.info(f"[{req_id}] Akış üreticisi tamamlandı, olay işaretlendi")

            stream_gen_func = create_stream_generator_from_helper(completion_event)
            if not result_future.done():
                result_future.set_result(StreamingResponse(stream_gen_func, media_type="text/event-stream"))
            else:
                if not completion_event.is_set():
                    completion_event.set()
            
            return completion_event, submit_button_locator, check_client_disconnected

        except Exception as e:
            logger.error(f"[{req_id}] Sradan veri aks alnrken hata olustu: {e}", exc_info=True)
            if completion_event and not completion_event.is_set():
                completion_event.set()
            raise

    else:  # aks ds
        content = None
        reasoning_content = None
        functions = None
        final_data_from_aux_stream = None

        async for raw_data in use_stream_response(req_id):
            check_client_disconnected(f"Akış dışı yardımcı akış döngüsü ({req_id})")
            
            # Verinin sözlük formatında olduğunu doğrula
            if isinstance(raw_data, str):
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    logger.warning(f"[{req_id}] Akış dışı JSON verisi çözülemedi: {raw_data}")
                    continue
            elif isinstance(raw_data, dict):
                data = raw_data
            else:
                logger.warning(f"[{req_id}] Akış dışı bilinmeyen veri türü: {type(raw_data)}")
                continue
            
            # Verinin sözlük olduğunu tekrar teyit et
            if not isinstance(data, dict):
                logger.warning(f"[{req_id}] Akış dışı veri sözlük formatında değil: {data}")
                continue
                
            final_data_from_aux_stream = data
            if data.get("done"):
                content = data.get("body")
                reasoning_content = data.get("reason")
                functions = data.get("function")
                break
        
        if final_data_from_aux_stream and final_data_from_aux_stream.get("reason") == "internal_timeout":
            logger.error(f"[{req_id}] Akış dışı istek yardımcı akışta iç zaman aşımına uğradı")
            raise HTTPException(status_code=502, detail=f"[{req_id}] Yardımcı akış işlemede hata (iç zaman aşımı)")

        if final_data_from_aux_stream and final_data_from_aux_stream.get("done") is True and content is None:
            logger.error(f"[{req_id}] Akış dışı istek yardımcı akışta tamamlandı ancak içerik gelmedi")
            raise HTTPException(status_code=502, detail=f"[{req_id}] Yardımcı akış tamamlandı fakat içerik sağlanmadı")

        model_name_for_json = current_ai_studio_model_id or MODEL_NAME
        message_payload = {"role": "assistant", "content": content}
        finish_reason_val = "stop"

        if functions and len(functions) > 0:
            tool_calls_list = []
            for func_idx, function_call_data in enumerate(functions):
                tool_calls_list.append({
                    "id": f"call_{generate_random_string(24)}",
                    "index": func_idx,
                    "type": "function",
                    "function": {
                        "name": function_call_data["name"],
                        "arguments": json.dumps(function_call_data["params"]),
                    },
                })
            message_payload["tool_calls"] = tool_calls_list
            finish_reason_val = "tool_calls"
            message_payload["content"] = None
        
        if reasoning_content:
            message_payload["reasoning_content"] = reasoning_content

        # hesaplamaktokenkullanmakistatistik
        usage_stats = calculate_usage_stats(
            [msg.model_dump() for msg in request.messages],
            content or "",
            reasoning_content
        )

        response_payload = {
            "id": f"{CHAT_COMPLETION_ID_PREFIX}{req_id}-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name_for_json,
            "choices": [{
                "index": 0,
                "message": message_payload,
                "finish_reason": finish_reason_val,
                "native_finish_reason": finish_reason_val,
            }],
            "usage": usage_stats
        }

        if not result_future.done():
            result_future.set_result(JSONResponse(content=response_payload))
        return None


async def _handle_playwright_response(req_id: str, request: ChatCompletionRequest, page: AsyncPage, 
                                    context: dict, result_future: Future, submit_button_locator: Locator, 
                                    check_client_disconnected: Callable) -> Optional[Tuple[Event, Locator, Callable]]:
    """Yanıtı Playwright ile işler"""
    from server import logger
    
    is_streaming = request.stream
    current_ai_studio_model_id = context.get('current_ai_studio_model_id')
    
    logger.info(f"[{req_id}] Yanıt öğeleri konumlandırılıyor...")
    response_container = page.locator(RESPONSE_CONTAINER_SELECTOR).last
    response_element = response_container.locator(RESPONSE_TEXT_SELECTOR)
    
    try:
        await expect_async(response_container).to_be_attached(timeout=20000)
        check_client_disconnected("After Response Container Attached: ")
        await expect_async(response_element).to_be_attached(timeout=90000)
        logger.info(f"[{req_id}] Yanıt öğeleri bulundu.")
    except (PlaywrightAsyncError, asyncio.TimeoutError, ClientDisconnectedError) as locate_err:
        if isinstance(locate_err, ClientDisconnectedError):
            raise
        logger.error(f"[{req_id}] ❌ Yanıt öğeleri konumlandırılırken hata veya zaman aşımı: {locate_err}")
        await save_error_snapshot(f"response_locate_error_{req_id}")
        raise HTTPException(status_code=502, detail=f"[{req_id}] AI Studio yanıt öğesi konumlandırılamadı: {locate_err}")
    except Exception as locate_exc:
        logger.exception(f"[{req_id}] ❌ Yanıt öğeleri konumlandırılırken beklenmeyen hata")
        await save_error_snapshot(f"response_locate_unexpected_{req_id}")
        raise HTTPException(status_code=500, detail=f"[{req_id}] Yanıt öğeleri konumlandırılırken beklenmeyen hata: {locate_exc}")

    check_client_disconnected("After Response Element Located: ")

    if is_streaming:
        completion_event = Event()

        async def create_response_stream_generator():
            # Veri alım durumunu işaretle
            data_receiving = False

            try:
                # PageController kullanarak yanıtı al
                page_controller = PageController(page, logger, req_id)
                final_content = await page_controller.get_response(check_client_disconnected)

                # Veri alındığını işaretle
                data_receiving = True

                # Akış yanıtlarını oluştur - Markdown yapısını koru
                # Satır bazında parçalayarak yeni satırları ve Markdown'ı koru
                lines = final_content.split('\n')
                for line_idx, line in enumerate(lines):
                    # İstemci bağlantısının kopup kopmadığını kontrol et
                    try:
                        check_client_disconnected(f"Playwright akış oluşturucu döngüsü ({req_id})")
                    except ClientDisconnectedError:
                        logger.info(f"[{req_id}] Playwright akış üreticisinde istemci bağlantısı kesildi")
                        # Müşteri veri alırken bağlantı kesildiyse done sinyalini ayarla
                        if data_receiving and not completion_event.is_set():
                            logger.info(f"[{req_id}] Playwright verisi alınırken istemci bağlantısı kesildi, done sinyali gönderiliyor")
                            completion_event.set()
                        break

                    # Satır içeriğini gönder (boş satırlar dahil, Markdown formatını koru)
                    if line:  # Boş olmayan satırlar karakter bazında parçalanır
                        chunk_size = 5  # Hız ve deneyimi dengelemek için 5 karakterlik parçalara böl
                        for i in range(0, len(line), chunk_size):
                            chunk = line[i:i+chunk_size]
                            yield generate_sse_chunk(chunk, req_id, current_ai_studio_model_id or MODEL_NAME)
                            await asyncio.sleep(0.03)  # Orta düzeyde gönderim hızı

                    # Satır sonu karakterlerini ekle (son satır hariç)
                    if line_idx < len(lines) - 1:
                        yield generate_sse_chunk('\n', req_id, current_ai_studio_model_id or MODEL_NAME)
                        await asyncio.sleep(0.01)
                
                # Kullanım istatistiklerini hesapla ve tamamlama bloğunu gönder
                usage_stats = calculate_usage_stats(
                    [msg.model_dump() for msg in request.messages],
                    final_content,
                    ""  # Playwright modunda reasoning içeriği yok
                )
                logger.info(f"[{req_id}] Playwright modunda hesaplanan token kullanım istatistikleri: {usage_stats}")
                
                # Kullanım istatistiklerini içeren tamamlama bloğunu gönder
                yield generate_sse_stop_chunk(req_id, current_ai_studio_model_id or MODEL_NAME, "stop", usage_stats)
                
            except ClientDisconnectedError:
                logger.info(f"[{req_id}] Playwright akış üreticisinde istemci bağlantısı kesildi")
                # Müşterinin bağlantısı kesildiyse done sinyalini ayarla
                if data_receiving and not completion_event.is_set():
                    logger.info(f"[{req_id}] Playwright akışında istemci bağlantısı kesildi, done sinyali gönderiliyor")
                    completion_event.set()
            except Exception as e:
                logger.error(f"[{req_id}] Playwright akış üreticisi çalışırken hata oluştu: {e}", exc_info=True)
                # İstemciye hata mesajı gönder
                try:
                    yield generate_sse_chunk(f"\n\n[hata: {str(e)}]", req_id, current_ai_studio_model_id or MODEL_NAME)
                    yield generate_sse_stop_chunk(req_id, current_ai_studio_model_id or MODEL_NAME)
                except Exception:
                    pass  # Hata mesajı gönderilemezse işlemin son kısmına devam et
            finally:
                # Olayın işaretlendiğinden emin ol
                if not completion_event.is_set():
                    completion_event.set()
                    logger.info(f"[{req_id}] Playwright akış üreticisi tamamlandı ve olay işaretlendi")

        stream_gen_func = create_response_stream_generator()
        if not result_future.done():
            result_future.set_result(StreamingResponse(stream_gen_func, media_type="text/event-stream"))
        
        return completion_event, submit_button_locator, check_client_disconnected
    else:
        # PageController kullanarak yanıtı al
        page_controller = PageController(page, logger, req_id)
        final_content = await page_controller.get_response(check_client_disconnected)
        
        # Token kullanım istatistiklerini hesapla
        usage_stats = calculate_usage_stats(
            [msg.model_dump() for msg in request.messages],
            final_content,
            ""  # Playwright modunda reasoning içeriği yok
        )
        logger.info(f"[{req_id}] Playwright modunda hesaplanan token kullanım istatistikleri: {usage_stats}")
        
        response_payload = {
            "id": f"{CHAT_COMPLETION_ID_PREFIX}{req_id}-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": current_ai_studio_model_id or MODEL_NAME,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": final_content},
                "finish_reason": "stop"
            }],
            "usage": usage_stats
        }
        
        if not result_future.done():
            result_future.set_result(JSONResponse(content=response_payload))
        
        return None


async def _cleanup_request_resources(req_id: str, disconnect_check_task: Optional[asyncio.Task], 
                                   completion_event: Optional[Event], result_future: Future, 
                                   is_streaming: bool) -> None:
    """Talep edilen kaynaklar temizle"""
    from server import logger
    
    if disconnect_check_task and not disconnect_check_task.done():
        disconnect_check_task.cancel()
        try: 
            await disconnect_check_task
        except asyncio.CancelledError: 
            pass
        except Exception as task_clean_err: 
            logger.error(f"[{req_id}] Gorevi temizlerken bir hata olustu: {task_clean_err}")
    
    logger.info(f"[{req_id}] Isleme tamamland。")
    
    if is_streaming and completion_event and not completion_event.is_set() and (result_future.done() and result_future.exception() is not None):
        logger.warning(f"[{req_id}] Akış isteğinde istisna yakalandı; tamamlanma olayı işaretlendi.")
        completion_event.set()


async def _process_request_refactored(
    req_id: str,
    request: ChatCompletionRequest,
    http_request: Request,
    result_future: Future
) -> Optional[Tuple[Event, Locator, Callable[[str], bool]]]:
    """Cekirdek istek isleme islevi - Yeniden duzenlenmis surum"""

    # optimizasyon：Herhangi bir isleme baslamadan once istemci baglant durumunu aktif olarak alglayn
    is_connected = await _test_client_connection(req_id, http_request)
    if not is_connected:
        from server import logger
        logger.info(f"[{req_id}] ✅ Temel islemeden once musteri baglants tespit edildi，Kaynaklardan tasarruf etmek icin erken ckn")
        if not result_future.done():
            result_future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] Islem baslamadan once istemcinin baglants kesildi"))
        return None

    context = await _initialize_request_context(req_id, request)
    context = await _analyze_model_requirements(req_id, context, request)
    
    client_disconnected_event, disconnect_check_task, check_client_disconnected = await _setup_disconnect_monitoring(
        req_id, http_request, result_future
    )
    
    page = context['page']
    submit_button_locator = page.locator(SUBMIT_BUTTON_SELECTOR) if page else None
    completion_event = None
    
    try:
        await _validate_page_status(req_id, context, check_client_disconnected)
        
        page_controller = PageController(page, context['logger'], req_id)

        await _handle_model_switching(req_id, context, check_client_disconnected)
        await _handle_parameter_cache(req_id, context)
        
        prepared_prompt,image_list = await _prepare_and_validate_request(req_id, request, check_client_disconnected)

        # kullanmakPageControllerSayfa etkilesimlerini yonetin
        # Fark etme：Kilit acldktan sonra sohbet gecmisinin temizlenmesi, islenmek uzere sraya tasnd.

        await page_controller.adjust_parameters(
            request.model_dump(exclude_none=True), # kullanmak exclude_none=True Gecmekten kacnmakNonedeger
            context['page_params_cache'],
            context['params_cache_lock'],
            context['model_id_to_use'],
            context['parsed_model_list'],
            check_client_disconnected
        )

        # optimizasyon：Bir istem gondermeden once musteri baglantsn tekrar kontrol edin，Gereksiz arka plan isteklerinden kacnn
        check_client_disconnected("Bir istem gondermeden once son cek")

        await page_controller.submit_prompt(prepared_prompt,image_list, check_client_disconnected)
        
        # Yanıt işleme burada yapılmaya devam eder; akış olup olmadığını belirler ve future'ı ayarlar
        response_result = await _handle_response_processing(
            req_id, request, page, context, result_future, submit_button_locator, check_client_disconnected
        )
        
        if response_result:
            completion_event, _, _ = response_result
        
        return completion_event, submit_button_locator, check_client_disconnected
        
    except ClientDisconnectedError as disco_err:
        context['logger'].info(f"[{req_id}] İstemci bağlantısı kesildi sinyali yakalandı: {disco_err}")
        if not result_future.done():
             result_future.set_exception(HTTPException(status_code=499, detail=f"[{req_id}] Client disconnected during processing."))
    except HTTPException as http_err:
        context['logger'].warning(f"[{req_id}] yakaland HTTP anormal: {http_err.status_code} - {http_err.detail}")
        if not result_future.done():
            result_future.set_exception(http_err)
    except PlaywrightAsyncError as pw_err:
        context['logger'].error(f"[{req_id}] yakaland Playwright hata: {pw_err}")
        await save_error_snapshot(f"process_playwright_error_{req_id}")
        if not result_future.done():
            result_future.set_exception(HTTPException(status_code=502, detail=f"[{req_id}] Playwright interaction failed: {pw_err}"))
    except Exception as e:
        context['logger'].exception(f"[{req_id}] Beklenmeyen bir hata yakalandı")
        await save_error_snapshot(f"process_unexpected_error_{req_id}")
        if not result_future.done():
            result_future.set_exception(HTTPException(status_code=500, detail=f"[{req_id}] Unexpected server error: {e}"))
    finally:
        await _cleanup_request_resources(req_id, disconnect_check_task, completion_event, result_future, request.stream)
