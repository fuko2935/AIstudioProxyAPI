"""
Sabit değerlerin tanımlandığı yapılandırma modülü.
Model adları, belirteçler, dosya adları gibi değişmeyen değerleri içerir.
"""

import os
import json

# Sabit zaman damgaları gerektiren değerler için yer tutucu
_FALLBACK_CREATED_TS = 0
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# --- Modellerle ilgili sabitler ---
MODEL_NAME = os.environ.get('MODEL_NAME', 'Qwen-Proxy-API')
CHAT_COMPLETION_ID_PREFIX = os.environ.get('CHAT_COMPLETION_ID_PREFIX', 'chatcmpl-')
DEFAULT_FALLBACK_MODEL_ID = os.environ.get('DEFAULT_FALLBACK_MODEL_ID', "qwen3-max")

# --- Varsayılan model geri dönüş listesi ---
DEFAULT_QWEN_MODELS = [
    {
        "id": "qwen3-max",
        "object": "model",
        "created": _FALLBACK_CREATED_TS,
        "owned_by": "qwen",
        "display_name": "Qwen3-Max",
        "description": "Flagship Qwen3 model for general reasoning and complex problem solving.",
    },
    {
        "id": "qwen3-vl-235b",
        "object": "model",
        "created": _FALLBACK_CREATED_TS,
        "owned_by": "qwen",
        "display_name": "Qwen3-VL-235B",
        "description": "Large multimodal model capable of advanced vision-language understanding.",
    },
    {
        "id": "qwq-32b",
        "object": "model",
        "created": _FALLBACK_CREATED_TS,
        "owned_by": "qwen",
        "display_name": "QwQ-32B",
        "description": "Preview reasoning specialist derived from the Qwen QwQ series.",
    },
    {
        "id": "qwen2.5-max",
        "object": "model",
        "created": _FALLBACK_CREATED_TS,
        "owned_by": "qwen",
        "display_name": "Qwen2.5-Max",
        "description": "High capacity Qwen2.5 model retained for backwards compatibility.",
    },
]

# --- Varsayılan parametre değerleri ---
DEFAULT_TEMPERATURE = float(os.environ.get('DEFAULT_TEMPERATURE', '1.0'))
DEFAULT_MAX_OUTPUT_TOKENS = int(os.environ.get('DEFAULT_MAX_OUTPUT_TOKENS', '65536'))
DEFAULT_TOP_P = float(os.environ.get('DEFAULT_TOP_P', '0.95'))
# --- Varsayılan özellik anahtarları ---
ENABLE_URL_CONTEXT = os.environ.get('ENABLE_URL_CONTEXT', 'false').lower() in ('true', '1', 'yes')
ENABLE_THINKING_BUDGET = os.environ.get('ENABLE_THINKING_BUDGET', 'false').lower() in ('true', '1', 'yes')
DEFAULT_THINKING_BUDGET = int(os.environ.get('DEFAULT_THINKING_BUDGET', '8192'))
ENABLE_GOOGLE_SEARCH = os.environ.get('ENABLE_GOOGLE_SEARCH', 'false').lower() in ('true', '1', 'yes')

# Varsayılan durdurma dizileri - JSON formatını destekler
try:
    DEFAULT_STOP_SEQUENCES = json.loads(os.environ.get('DEFAULT_STOP_SEQUENCES', '["Kullanıcı:"]'))
except (json.JSONDecodeError, TypeError):
    DEFAULT_STOP_SEQUENCES = ["Kullanıcı:"]  # Varsayılan değere geri dön

# --- URL kalıpları ---
AI_STUDIO_URL_PATTERN = os.environ.get('AI_STUDIO_URL_PATTERN', 'chat.qwen.ai/')
MODELS_ENDPOINT_URL_CONTAINS = os.environ.get('MODELS_ENDPOINT_URL_CONTAINS', "api/chat")

# --- Girdi belirteçleri ---
USER_INPUT_START_MARKER_SERVER = os.environ.get('USER_INPUT_START_MARKER_SERVER', "__USER_INPUT_START__")
USER_INPUT_END_MARKER_SERVER = os.environ.get('USER_INPUT_END_MARKER_SERVER', "__USER_INPUT_END__")

# --- Dosya adı sabitleri ---
EXCLUDED_MODELS_FILENAME = os.environ.get('EXCLUDED_MODELS_FILENAME', "excluded_models.txt")

# --- Akış durum bilgisi ---
STREAM_TIMEOUT_LOG_STATE = {
    "consecutive_timeouts": 0,
    "last_error_log_time": 0.0,  # time.monotonic() kullanır
    "suppress_until_time": 0.0,  # time.monotonic() kullanır
    "max_initial_errors": int(os.environ.get('STREAM_MAX_INITIAL_ERRORS', '3')),
    "warning_interval_after_suppress": float(os.environ.get('STREAM_WARNING_INTERVAL_AFTER_SUPPRESS', '60.0')),
    "suppress_duration_after_initial_burst": float(os.environ.get('STREAM_SUPPRESS_DURATION_AFTER_INITIAL_BURST', '400.0')),
}
