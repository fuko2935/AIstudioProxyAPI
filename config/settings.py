"""
Ana ayarlar modülü.
Ortam değişkenleri, yol tanımları, proxy ve diğer çalışma zamanı ayarlarını içerir.
"""

import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# --- Küresel log kontrol ayarları ---
DEBUG_LOGS_ENABLED = os.environ.get('DEBUG_LOGS_ENABLED', 'false').lower() in ('true', '1', 'yes')
TRACE_LOGS_ENABLED = os.environ.get('TRACE_LOGS_ENABLED', 'false').lower() in ('true', '1', 'yes')

# --- Kimlik doğrulama ayarları ---
AUTO_SAVE_AUTH = os.environ.get('AUTO_SAVE_AUTH', '').lower() in ('1', 'true', 'yes')
AUTH_SAVE_TIMEOUT = int(os.environ.get('AUTH_SAVE_TIMEOUT', '30'))
AUTO_CONFIRM_LOGIN = os.environ.get('AUTO_CONFIRM_LOGIN', 'true').lower() in ('1', 'true', 'yes')

# --- Yol tanımları ---
AUTH_PROFILES_DIR = os.path.join(os.path.dirname(__file__), '..', 'auth_profiles')
ACTIVE_AUTH_DIR = os.path.join(AUTH_PROFILES_DIR, 'active')
SAVED_AUTH_DIR = os.path.join(AUTH_PROFILES_DIR, 'saved')
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
APP_LOG_FILE_PATH = os.path.join(LOG_DIR, 'app.log')

def get_environment_variable(key: str, default: str = '') -> str:
    """Bir ortam değişkeninin değerini döndürür"""
    return os.environ.get(key, default)

def get_boolean_env(key: str, default: bool = False) -> bool:
    """Bir ortam değişkenini boolean olarak çözümler"""
    value = os.environ.get(key, '').lower()
    if default:
        return value not in ('false', '0', 'no', 'off')
    else:
        return value in ('true', '1', 'yes', 'on')

def get_int_env(key: str, default: int = 0) -> int:
    """Bir ortam değişkenini tam sayı olarak döndürür"""
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default

# --- Proxy yapılandırması ---
# Not: Proxy ayarları artık STREAM_PORT ortam değişkenine göre api_utils/app.py içinde dinamik olarak belirlenir
NO_PROXY_ENV = os.environ.get('NO_PROXY')

# --- Script enjeksiyonu ayarları ---
ENABLE_SCRIPT_INJECTION = get_boolean_env('ENABLE_SCRIPT_INJECTION', True)
USERSCRIPT_PATH = get_environment_variable('USERSCRIPT_PATH', 'browser_utils/more_modles.js')
# Not: MODEL_CONFIG_PATH artık kullanılmıyor; model verileri userscript içinden okunuyor

# --- Qwen'e özgü ayarlar ---
ENABLE_QWEN_LOGIN_SUPPORT = get_boolean_env('ENABLE_QWEN_LOGIN_SUPPORT', False)
