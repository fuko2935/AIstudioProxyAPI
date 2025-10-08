"""
Zamanlayıcı ve zaman aşımı yapılandırmalarını içeren modül.
Tüm zaman aşımı değerleri, poll aralıkları ve diğer süre parametrelerini toplar.
"""

import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# --- Yanıt bekleme ayarları ---
RESPONSE_COMPLETION_TIMEOUT = int(os.environ.get('RESPONSE_COMPLETION_TIMEOUT', '300000'))  # 5 minutes total timeout (in ms)
INITIAL_WAIT_MS_BEFORE_POLLING = int(os.environ.get('INITIAL_WAIT_MS_BEFORE_POLLING', '500'))  # ms, initial wait before polling for response completion

# --- Polling aralıkları ---
POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL', '300'))  # ms
POLLING_INTERVAL_STREAM = int(os.environ.get('POLLING_INTERVAL_STREAM', '180'))  # ms

# --- Sessizlik zaman aşımı ---
SILENCE_TIMEOUT_MS = int(os.environ.get('SILENCE_TIMEOUT_MS', '60000'))  # ms

# --- Sayfa işlemi zaman aşımı ---
POST_SPINNER_CHECK_DELAY_MS = int(os.environ.get('POST_SPINNER_CHECK_DELAY_MS', '500'))
FINAL_STATE_CHECK_TIMEOUT_MS = int(os.environ.get('FINAL_STATE_CHECK_TIMEOUT_MS', '1500'))
POST_COMPLETION_BUFFER = int(os.environ.get('POST_COMPLETION_BUFFER', '700'))

# --- Sohbet temizleme zaman aşımı ---
CLEAR_CHAT_VERIFY_TIMEOUT_MS = int(os.environ.get('CLEAR_CHAT_VERIFY_TIMEOUT_MS', '5000'))
CLEAR_CHAT_VERIFY_INTERVAL_MS = int(os.environ.get('CLEAR_CHAT_VERIFY_INTERVAL_MS', '2000'))

# --- Tıklama ve pano işlemi zaman aşımı ---
CLICK_TIMEOUT_MS = int(os.environ.get('CLICK_TIMEOUT_MS', '3000'))
CLIPBOARD_READ_TIMEOUT_MS = int(os.environ.get('CLIPBOARD_READ_TIMEOUT_MS', '3000'))

# --- Element bekleme zaman aşımı ---
WAIT_FOR_ELEMENT_TIMEOUT_MS = int(os.environ.get('WAIT_FOR_ELEMENT_TIMEOUT_MS', '10000'))  # Timeout for waiting for elements like overlays

# --- Akışa ilişkin ayarlar ---
PSEUDO_STREAM_DELAY = float(os.environ.get('PSEUDO_STREAM_DELAY', '0.01'))
