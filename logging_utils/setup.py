import logging
import logging.handlers
import os
import sys
from typing import Tuple

from config import LOG_DIR, ACTIVE_AUTH_DIR, SAVED_AUTH_DIR, APP_LOG_FILE_PATH
from models import StreamToLogger, WebSocketLogHandler, WebSocketConnectionManager


def setup_server_logging(
    logger_instance: logging.Logger,
    log_ws_manager: WebSocketConnectionManager,
    log_level_name: str = "INFO",
    redirect_print_str: str = "false"
) -> Tuple[object, object]:
    """
    Sunucu log sistemini kur

    Args:
        logger_instance: Ana logger örneği
        log_ws_manager: WebSocket bağlantı yöneticisi
        log_level_name: Log seviyesi adı
        redirect_print_str: Print çıktısı yönlendirilsin mi

    Returns:
        Tuple[object, object]: Orijinal stdout ve stderr akışları
    """
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    redirect_print = redirect_print_str.lower() in ('true', '1', 'yes')
    
    # Gerekli dizinleri oluştur
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(ACTIVE_AUTH_DIR, exist_ok=True)
    os.makedirs(SAVED_AUTH_DIR, exist_ok=True)
    
    # Dosya log formatörünü ayarla
    file_log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s')
    
    # Mevcut handler'ları temizle
    if logger_instance.hasHandlers():
        logger_instance.handlers.clear()
    logger_instance.setLevel(log_level)
    logger_instance.propagate = False
    
    # Eski log dosyalarını kaldır
    if os.path.exists(APP_LOG_FILE_PATH):
        try:
            os.remove(APP_LOG_FILE_PATH)
        except OSError as e:
            print(f"Uyarı (setup_server_logging): Eski app.log dosyası '{APP_LOG_FILE_PATH}' kaldırma girişimi başarısız: {e}. Mode='w' ile kesmeye güvenecek.", file=sys.__stderr__)
    
    # Dosya handler'ı ekle
    file_handler = logging.handlers.RotatingFileHandler(
        APP_LOG_FILE_PATH, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8', mode='w'
    )
    file_handler.setFormatter(file_log_formatter)
    logger_instance.addHandler(file_handler)
    
    # WebSocket handler'ı ekle
    if log_ws_manager is None:
        print("Ciddi uyarı (setup_server_logging): log_ws_manager başlatılmadı! WebSocket log özelliği kullanılamayacak.", file=sys.__stderr__)
    else:
        ws_handler = WebSocketLogHandler(log_ws_manager)
        ws_handler.setLevel(logging.INFO)
        logger_instance.addHandler(ws_handler)
    
    # Konsol handler'ı ekle
    console_server_log_formatter = logging.Formatter('%(asctime)s - %(levelname)s [SERVER] - %(message)s')
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(console_server_log_formatter)
    console_handler.setLevel(log_level)
    logger_instance.addHandler(console_handler)
    
    # Orijinal akışları kaydet
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # Print çıktısını yönlendir (eğer gerekliyse)
    if redirect_print:
        print("--- Not: server.py print çıktısını log sistemine yönlendiriyor (dosya, WebSocket ve konsol logger'larına) ---", file=original_stderr)
        stdout_redirect_logger = logging.getLogger("AIStudioProxyServer.stdout")
        stdout_redirect_logger.setLevel(logging.INFO)
        stdout_redirect_logger.propagate = True
        sys.stdout = StreamToLogger(stdout_redirect_logger, logging.INFO)
        stderr_redirect_logger = logging.getLogger("AIStudioProxyServer.stderr")
        stderr_redirect_logger.setLevel(logging.ERROR)
        stderr_redirect_logger.propagate = True
        sys.stderr = StreamToLogger(stderr_redirect_logger, logging.ERROR)
    else:
        print("--- server.py'nin print çıktısı log sistemine yönlendirilmedi (orijinal stdout/stderr kullanılacak) ---", file=original_stderr)
    
    # Üçüncü parti kütüphane log seviyelerini yapılandır
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.ERROR)
    
    # Başlatma bilgilerini kaydet
    logger_instance.info("=" * 5 + " AIStudioProxyServer log sistemi lifespan'de başlatıldı " + "=" * 5)
    logger_instance.info(f"Log seviyesi ayarlandı: {logging.getLevelName(log_level)}")
    logger_instance.info(f"Log dosya yolu: {APP_LOG_FILE_PATH}")
    logger_instance.info(f"Konsol log handler'ı eklendi.")
    logger_instance.info(f"Print yönlendirmesi (SERVER_REDIRECT_PRINT env değişkeni tarafından kontrol edilir): {'Etkin' if redirect_print else 'Devre dışı'}")
    
    return original_stdout, original_stderr


def restore_original_streams(original_stdout: object, original_stderr: object) -> None:
    """
    Orijinal stdout ve stderr akışlarını geri yükle

    Args:
        original_stdout: Orijinal stdout akışı
        original_stderr: Orijinal stderr akışı
    """
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    print("server.py'nin orijinal stdout ve stderr akışları geri yüklendi.", file=sys.__stderr__)