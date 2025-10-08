import argparse # Yeni içe aktarma
from flask import Flask, request, jsonify
import requests
import time
import uuid
import logging
import json
import sys # Yeni içe aktarma
from typing import Dict, Any
from datetime import datetime, UTC

# Özel log Handler'ı, tazelemeyi sağlar
class FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
            self.flush()
        except Exception:
            self.handleError(record)

# Log yapılandırması (Türkçe'ye değiştirildi)
log_format = '%(asctime)s [%(levelname)s] %(message)s'
formatter = logging.Formatter(log_format)

# sys.stderr'i açıkça hedefleyen bir handler oluştur ve özel FlushingStreamHandler kullan
# sys.stderr alt süreçte gui_launcher.py'nin PIPE'ı tarafından yakalanmalı
stderr_handler = FlushingStreamHandler(sys.stderr)
stderr_handler.setFormatter(formatter)
stderr_handler.setLevel(logging.INFO)

# Kök logger'ı al ve handler'ımızı ekle
# Bu, tüm kök logger'a yayılmış logların (Flask ve Werkzeug'unkiler dahil, kendi özel handler'ları yoksa)
# bu handler'dan geçmesini sağlar。
root_logger = logging.getLogger()
# basicConfig veya diğer kütüphaneler tarafından eklenen varsayılan handler'ları temizle, tekrarlanan logları veya beklenmeyen çıktıları önlemek için
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.addHandler(stderr_handler)
root_logger.setLevel(logging.INFO) # Kök logger seviyesinin de ayarlandığından emin ol

logger = logging.getLogger(__name__) # 'llm' adlı logger'ı al, kök logger yapılandırmasını miras alır

app = Flask(__name__)
# Flask'ın app.logger'ı varsayılan olarak root logger'a yayılır.
# Gerekirse app.logger ve werkzeug logger için ayrı ayrı yapılandırılabilir, ama genellikle root'a yayılmaları yeterlidir.
# Örneğin:
# app.logger.handlers.clear() # Flask'ın eklediği varsayılan handler'ı temizle
# app.logger.addHandler(stderr_handler)
# app.logger.setLevel(logging.INFO)
#
# werkzeug_logger = logging.getLogger('werkzeug')
# werkzeug_logger.handlers.clear()
# werkzeug_logger.addHandler(stderr_handler)
# werkzeug_logger.setLevel(logging.INFO)

# Model yapılandırmasını etkinleştir: Etkin model adlarını doğrudan tanımla
# Kullanıcı model adlarını ekleyebilir/silebilir, meta verileri dinamik olarak oluştur
ENABLED_MODELS = {
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
}

# API yapılandırması
API_URL = "" # main fonksiyonunda parametreye göre ayarlanacak
DEFAULT_MAIN_SERVER_PORT = 2048
# Lütfen kendi API anahtarınızla değiştirin (lütfen paylaşmayın)
API_KEY = "123456"

# Ollama sohbet yanıt veritabanını simüle et
OLLAMA_MOCK_RESPONSES = {
    "What is the capital of France?": "The capital of France is Paris.",
    "Tell me about AI.": "AI is the simulation of human intelligence in machines, enabling tasks like reasoning and learning.",
    "Hello": "Hi! How can I assist you today?"
}

@app.route("/", methods=["GET"])
def root_endpoint():
    """Ollama kök yolunu simüle et, 'Ollama is running' döndür"""
    logger.info("Kök yol isteği alındı")
    return "Ollama is running", 200

@app.route("/api/tags", methods=["GET"])
def tags_endpoint():
    """Ollama'nın /api/tags uç noktasını simüle et, etkin model listesini dinamik olarak oluştur"""
    logger.info("/api/tags isteği alındı")
    models = []
    for model_name in ENABLED_MODELS:
        # Aile çıkar: Model adından öneki çıkar (örn. "gpt-4o" -> "gpt")
        family = model_name.split('-')[0].lower() if '-' in model_name else model_name.lower()
        # Bilinen modeller için özel işleme
        if 'llama' in model_name:
            family = 'llama'
            format = 'gguf'
            size = 1234567890
            parameter_size = '405B' if '405b' in model_name else 'unknown'
            quantization_level = 'Q4_0'
        elif 'mistral' in model_name:
            family = 'mistral'
            format = 'gguf'
            size = 1234567890
            parameter_size = 'unknown'
            quantization_level = 'unknown'
        else:
            format = 'unknown'
            size = 9876543210
            parameter_size = 'unknown'
            quantization_level = 'unknown'

        models.append({
            "name": model_name,
            "model": model_name,
            "modified_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "size": size,
            "digest": str(uuid.uuid4()),
            "details": {
                "parent_model": "",
                "format": format,
                "family": family,
                "families": [family],
                "parameter_size": parameter_size,
                "quantization_level": quantization_level
            }
        })
    logger.info(f"{len(models)} model döndürüyor: {[m['name'] for m in models]}")
    return jsonify({"models": models}), 200

def generate_ollama_mock_response(prompt: str, model: str) -> Dict[str, Any]:
    """Simüle edilmiş Ollama sohbet yanıtı oluştur, /api/chat formatına uygun"""
    response_content = OLLAMA_MOCK_RESPONSES.get(
        prompt, f"Echo: {prompt} (Bu simüle edilmiş Ollama sunucusundan gelen yanıttır.)"
    )

    return {
        "model": model,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "message": {
            "role": "assistant",
            "content": response_content
        },
        "done": True,
        "total_duration": 123456789,
        "load_duration": 1234567,
        "prompt_eval_count": 10,
        "prompt_eval_duration": 2345678,
        "eval_count": 20,
        "eval_duration": 3456789
    }

def convert_api_to_ollama_response(api_response: Dict[str, Any], model: str) -> Dict[str, Any]:
    """API'nin OpenAI format yanıtını Ollama formatına dönüştür"""
    try:
        content = api_response["choices"][0]["message"]["content"]
        total_duration = api_response.get("usage", {}).get("total_tokens", 30) * 1000000
        prompt_tokens = api_response.get("usage", {}).get("prompt_tokens", 10)
        completion_tokens = api_response.get("usage", {}).get("completion_tokens", 20)

        return {
            "model": model,
            "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "message": {
                "role": "assistant",
                "content": content
            },
            "done": True,
            "total_duration": total_duration,
            "load_duration": 1234567,
            "prompt_eval_count": prompt_tokens,
            "prompt_eval_duration": prompt_tokens * 100000,
            "eval_count": completion_tokens,
            "eval_duration": completion_tokens * 100000
        }
    except KeyError as e:
        logger.error(f"API yanıtı dönüştürme başarısız: Anahtar eksik {str(e)}")
        return {"error": f"Geçersiz API yanıt formatı: Anahtar eksik {str(e)}"}

def print_request_params(data: Dict[str, Any], endpoint: str) -> None:
    """İstek parametrelerini yazdır"""
    model = data.get("model", "Belirtilmedi")
    temperature = data.get("temperature", "Belirtilmedi")
    stream = data.get("stream", False)

    messages_info = []
    for msg in data.get("messages", []):
        role = msg.get("role", "Bilinmiyor")
        content = msg.get("content", "")
        content_preview = content[:50] + "..." if len(content) > 50 else content
        messages_info.append(f"[{role}] {content_preview}")

    params_str = {
        "Uç Nokta": endpoint,
        "Model": model,
        "Sıcaklık": temperature,
        "Akış Çıktısı": stream,
        "Mesaj Sayısı": len(data.get("messages", [])),
        "Mesaj Önizlemesi": messages_info
    }

    logger.info(f"İstek parametreleri: {json.dumps(params_str, ensure_ascii=False, indent=2)}")

@app.route("/api/chat", methods=["POST"])
def ollama_chat_endpoint():
    """Ollama'nın /api/chat uç noktasını simüle et, tüm modeller kullanılabilir"""
    try:
        data = request.get_json()
        if not data or "messages" not in data:
            logger.error("Geçersiz istek: 'messages' alanı eksik")
            return jsonify({"error": "Geçersiz istek: 'messages' alanı eksik"}), 400

        messages = data.get("messages", [])
        if not messages or not isinstance(messages, list):
            logger.error("Geçersiz istek: 'messages' boş olmayan bir liste olmalı")
            return jsonify({"error": "Geçersiz istek: 'messages' boş olmayan bir liste olmalı"}), 400

        model = data.get("model", "llama3.2")
        user_message = next(
            (msg["content"] for msg in reversed(messages) if msg.get("role") == "user"),
            ""
        )
        if not user_message:
            logger.error("Kullanıcı mesajı bulunamadı")
            return jsonify({"error": "Kullanıcı mesajı bulunamadı"}), 400

        # İstek parametrelerini yazdır
        print_request_params(data, "/api/chat")

        logger.info(f"/api/chat isteği işleniyor, model: {model}")

        # Model sınırlamasını kaldır, tüm modeller API kullanır
        api_request = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": data.get("temperature", 0.7)
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }

        try:
            logger.info(f"İstek API'ye yönlendiriliyor: {API_URL}")
            response = requests.post(API_URL, json=api_request, headers=headers, timeout=300000)
            response.raise_for_status()
            api_response = response.json()
            ollama_response = convert_api_to_ollama_response(api_response, model)
            logger.info(f"API'den yanıt alındı, model: {model}")
            return jsonify(ollama_response), 200
        except requests.RequestException as e:
            logger.error(f"API isteği başarısız: {str(e)}")
            # API isteği başarısız olursa, simüle edilmiş yanıtı yedek olarak kullan
            logger.info(f"Simüle edilmiş yanıtı yedek olarak kullan, model: {model}")
            response = generate_ollama_mock_response(user_message, model)
            return jsonify(response), 200

    except Exception as e:
        logger.error(f"/api/chat sunucu hatası: {str(e)}")
        return jsonify({"error": f"Sunucu hatası: {str(e)}"}), 500

@app.route("/v1/chat/completions", methods=["POST"])
def api_chat_endpoint():
    """API'nin /v1/chat/completions uç noktasına yönlendir ve Ollama formatına dönüştür"""
    try:
        data = request.get_json()
        if not data or "messages" not in data:
            logger.error("Geçersiz istek: 'messages' alanı eksik")
            return jsonify({"error": "Geçersiz istek: 'messages' alanı eksik"}), 400

        messages = data.get("messages", [])
        if not messages or not isinstance(messages, list):
            logger.error("Geçersiz istek: 'messages' boş olmayan bir liste olmalı")
            return jsonify({"error": "Geçersiz istek: 'messages' boş olmayan bir liste olmalı"}), 400

        model = data.get("model", "grok-3")
        user_message = next(
            (msg["content"] for msg in reversed(messages) if msg.get("role") == "user"),
            ""
        )
        if not user_message:
            logger.error("Kullanıcı mesajı bulunamadı")
            return jsonify({"error": "Kullanıcı mesajı bulunamadı"}), 400

        # İstek parametrelerini yazdır
        print_request_params(data, "/v1/chat/completions")

        logger.info(f"/v1/chat/completions isteği işleniyor, model: {model}")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }

        try:
            logger.info(f"İstek API'ye yönlendiriliyor: {API_URL}")
            response = requests.post(API_URL, json=data, headers=headers, timeout=300000)
            response.raise_for_status()
            api_response = response.json()
            ollama_response = convert_api_to_ollama_response(api_response, model)
            logger.info(f"API'den yanıt alındı, model: {model}")
            return jsonify(ollama_response), 200
        except requests.RequestException as e:
            logger.error(f"API isteği başarısız: {str(e)}")
            return jsonify({"error": f"API isteği başarısız: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"/v1/chat/completions sunucu hatası: {str(e)}")
        return jsonify({"error": f"Sunucu hatası: {str(e)}"}), 500

    def main():
        """Simüle sunucuyu başlat"""
    global API_URL # Değiştireceğimiz global değişkeni beyan et

    parser = argparse.ArgumentParser(description="LLM Mock Service for AI Studio Proxy")
    parser.add_argument(
        "--main-server-port",
        type=int,
        default=DEFAULT_MAIN_SERVER_PORT,
        help=f"Port of the main AI Studio Proxy server (default: {DEFAULT_MAIN_SERVER_PORT})"
    )
    args = parser.parse_args()

    API_URL = f"http://localhost:{args.main_server_port}/v1/chat/completions"

    logger.info(f"Simüle Ollama ve API proxy sunucusu isteği yönlendirecek: {API_URL}")
    logger.info("Simüle Ollama ve API proxy sunucusu başlatılıyor, adres: http://localhost:11434")
    app.run(host="0.0.0.0", port=11434, debug=False)

if __name__ == "__main__":
    main()