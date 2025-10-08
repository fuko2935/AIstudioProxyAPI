#!/usr/bin/env python3
# launch_camoufox.py
import sys
import subprocess
import time
import re
import os
import signal
import atexit
import argparse
import select
import traceback
import json
import threading
import queue
import logging
import logging.handlers
import socket
import platform
import shutil

# --- Yeni içe aktarmalar ---
from dotenv import load_dotenv

# Sonraki modüllerin doğru ortam değişkenlerini almasını sağlamak için .env dosyasını önceden yükle
load_dotenv()

from config import ENABLE_QWEN_LOGIN_SUPPORT

import uvicorn
from server import app # FastAPI app nesnesini server.py dosyasından içe aktar
# -----------------

# launch_server'ı içe aktarmayı dene (dahili başlatma modu için, Camoufox davranışını simüle eder)
try:
    from camoufox.server import launch_server
    from camoufox import DefaultAddons # DefaultAddons'un AntiFingerprint içerdiğini varsay
except ImportError:
    if '--internal-launch' in sys.argv or any(arg.startswith('--internal-') for arg in sys.argv): # Dahili parametreleri daha geniş bir şekilde kontrol et
        print("❌ Kritik Hata: Dahili başlatma modu için 'camoufox.server.launch_server' ve 'camoufox.DefaultAddons' gerekli ancak içe aktarılamıyor.", file=sys.stderr)
        print("   Bu genellikle 'camoufox' paketinin doğru şekilde kurulmadığı veya PYTHONPATH içinde olmadığı anlamına gelir.", file=sys.stderr)
        sys.exit(1)
    else:
        launch_server = None
        DefaultAddons = None

# --- Yapılandırma Sabitleri ---
PYTHON_EXECUTABLE = sys.executable
ENDPOINT_CAPTURE_TIMEOUT = int(os.environ.get('ENDPOINT_CAPTURE_TIMEOUT', '45'))  # saniye (dev'den)
DEFAULT_SERVER_PORT = int(os.environ.get('DEFAULT_FASTAPI_PORT', '2048'))  # FastAPI sunucu portu
DEFAULT_CAMOUFOX_PORT = int(os.environ.get('DEFAULT_CAMOUFOX_PORT', '9222'))  # Camoufox hata ayıklama portu (dahili başlatma için gerekirse)
DEFAULT_STREAM_PORT = int(os.environ.get('STREAM_PORT', '3120'))  # Akış proxy sunucu portu
DEFAULT_HELPER_ENDPOINT = os.environ.get('GUI_DEFAULT_HELPER_ENDPOINT', '')  # Harici Yardımcı Uç Noktası
DEFAULT_AUTH_SAVE_TIMEOUT = int(os.environ.get('AUTH_SAVE_TIMEOUT', '30'))  # Kimlik doğrulama kaydetme zaman aşımı
DEFAULT_SERVER_LOG_LEVEL = os.environ.get('SERVER_LOG_LEVEL', 'INFO')  # Sunucu günlük seviyesi
AUTH_PROFILES_DIR = os.path.join(os.path.dirname(__file__), "auth_profiles")
ACTIVE_AUTH_DIR = os.path.join(AUTH_PROFILES_DIR, "active")
SAVED_AUTH_DIR = os.path.join(AUTH_PROFILES_DIR, "saved")
HTTP_PROXY = os.environ.get('HTTP_PROXY', '')
HTTPS_PROXY = os.environ.get('HTTPS_PROXY', '')
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
LAUNCHER_LOG_FILE_PATH = os.path.join(LOG_DIR, 'launch_app.log')

# --- Genel Süreç Tanımlayıcısı ---
camoufox_proc = None

# --- Günlük Kaydedici Örneği ---
logger = logging.getLogger("CamoufoxLauncher")

# --- WebSocket Uç Noktası Normal İfadesi ---
ws_regex = re.compile(r"(ws://\S+)")


# --- İş parçacığı güvenli çıktı kuyruğu işleme fonksiyonu (_enqueue_output) (dev'den - daha sağlam hata işleme) ---
def _enqueue_output(stream, stream_name, output_queue, process_pid_for_log="<BilinmeyenPID>"):
    log_prefix = f"[OkumaİşParçacığı-{stream_name}-PID:{process_pid_for_log}]"
    try:
        for line_bytes in iter(stream.readline, b''):
            if not line_bytes:
                break
            try:
                line_str = line_bytes.decode('utf-8', errors='replace')
                output_queue.put((stream_name, line_str))
            except Exception as decode_err:
                logger.warning(f"{log_prefix} Kod çözme hatası: {decode_err}. Orijinal veri (ilk 100 bayt): {line_bytes[:100]}")
                output_queue.put((stream_name, f"[Kod çözme hatası: {decode_err}] {line_bytes[:100]}...\n"))
    except ValueError:
        logger.debug(f"{log_prefix} ValueError (akış kapatılmış olabilir).")
    except Exception as e:
        logger.error(f"{log_prefix} Akış okunurken beklenmeyen bir hata oluştu: {e}", exc_info=True)
    finally:
        output_queue.put((stream_name, None))
        if hasattr(stream, 'close') and not stream.closed:
            try:
                stream.close()
            except Exception:
                pass
        logger.debug(f"{log_prefix} İş parçacığı sonlandırılıyor.")

# --- Bu başlatıcı betiği için günlük sistemini ayarla (setup_launcher_logging) (dev'den - başlangıçta günlüğü temizler) ---
def setup_launcher_logging(log_level=logging.INFO):
    os.makedirs(LOG_DIR, exist_ok=True)
    file_log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s')
    console_log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.setLevel(log_level)
    logger.propagate = False
    if os.path.exists(LAUNCHER_LOG_FILE_PATH):
        try:
            os.remove(LAUNCHER_LOG_FILE_PATH)
        except OSError:
            pass
    file_handler = logging.handlers.RotatingFileHandler(
        LAUNCHER_LOG_FILE_PATH, maxBytes=2*1024*1024, backupCount=3, encoding='utf-8', mode='w'
    )
    file_handler.setFormatter(file_log_formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(console_log_formatter)
    logger.addHandler(stream_handler)
    logger.info("=" * 30 + " Camoufox Başlatıcı Günlük Sistemi Başlatıldı " + "=" * 30)
    logger.info(f"Günlük seviyesi ayarlandı: {logging.getLevelName(logger.getEffectiveLevel())}")
    logger.info(f"Günlük dosyası yolu: {LAUNCHER_LOG_FILE_PATH}")

# --- Kimlik doğrulama dosyası dizinlerinin var olduğundan emin ol (ensure_auth_dirs_exist) ---
def ensure_auth_dirs_exist():
    logger.info("Kimlik doğrulama dosyası dizinleri kontrol ediliyor ve var olmaları sağlanıyor...")
    try:
        os.makedirs(ACTIVE_AUTH_DIR, exist_ok=True)
        logger.info(f"  ✓ Aktif kimlik doğrulama dizini hazır: {ACTIVE_AUTH_DIR}")
        os.makedirs(SAVED_AUTH_DIR, exist_ok=True)
        logger.info(f"  ✓ Kaydedilmiş kimlik doğrulama dizini hazır: {SAVED_AUTH_DIR}")
    except Exception as e:
        logger.error(f"  ❌ Kimlik doğrulama dizinleri oluşturulamadı: {e}", exc_info=True)
        sys.exit(1)

# --- Temizleme fonksiyonu (betik çıkışında çalışır) (dev'den - daha detaylı günlükleme ve kontroller) ---
def cleanup():
    global camoufox_proc
    logger.info("--- Temizleme prosedürü başlatılıyor (launch_camoufox.py) ---")
    if camoufox_proc and camoufox_proc.poll() is None:
        pid = camoufox_proc.pid
        logger.info(f"Camoufox dahili alt süreci sonlandırılıyor (PID: {pid})...")
        try:
            if sys.platform != "win32" and hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                try:
                    pgid = os.getpgid(pid)
                    logger.info(f"  Camoufox süreç grubuna (PGID: {pgid}) SIGTERM sinyali gönderiliyor...")
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    logger.info(f"  Camoufox süreç grubu (PID: {pid}) bulunamadı, doğrudan süreci sonlandırmaya çalışılıyor...")
                    camoufox_proc.terminate()
            else:
                if sys.platform == "win32":
                    logger.info(f"Süreç ağacına (PID: {pid}) sonlandırma isteği gönderiliyor")
                    subprocess.call(['taskkill', '/T', '/PID', str(pid)])
                else:
                    logger.info(f"  Camoufox'a (PID: {pid}) SIGTERM sinyali gönderiliyor...")
                    camoufox_proc.terminate()
            camoufox_proc.wait(timeout=5)
            logger.info(f"  ✓ Camoufox (PID: {pid}) SIGTERM ile başarıyla sonlandırıldı.")
        except subprocess.TimeoutExpired:
            logger.warning(f"  ⚠️ Camoufox (PID: {pid}) SIGTERM zaman aşımına uğradı. Zorla sonlandırmak için SIGKILL gönderiliyor...")
            if sys.platform != "win32" and hasattr(os, 'getpgid') and hasattr(os, 'killpg'):
                try:
                    pgid = os.getpgid(pid)
                    logger.info(f"  Camoufox süreç grubuna (PGID: {pgid}) SIGKILL sinyali gönderiliyor...")
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    logger.info(f"  Camoufox süreç grubu (PID: {pid}) SIGKILL sırasında bulunamadı, doğrudan zorla sonlandırmaya çalışılıyor...")
                    camoufox_proc.kill()
            else:
                if sys.platform == "win32":
                    logger.info(f"  Camoufox süreç ağacı (PID: {pid}) zorla sonlandırılıyor")
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(pid)])
                else:
                    camoufox_proc.kill()
            try:
                camoufox_proc.wait(timeout=2)
                logger.info(f"  ✓ Camoufox (PID: {pid}) SIGKILL ile başarıyla sonlandırıldı.")
            except Exception as e_kill:
                logger.error(f"  ❌ Camoufox (PID: {pid}) SIGKILL tamamlanması beklenirken hata oluştu: {e_kill}")
        except Exception as e_term:
            logger.error(f"  ❌ Camoufox (PID: {pid}) sonlandırılırken hata oluştu: {e_term}", exc_info=True)
        finally:
            if hasattr(camoufox_proc, 'stdout') and camoufox_proc.stdout and not camoufox_proc.stdout.closed:
                camoufox_proc.stdout.close()
            if hasattr(camoufox_proc, 'stderr') and camoufox_proc.stderr and not camoufox_proc.stderr.closed:
                camoufox_proc.stderr.close()
        camoufox_proc = None
    elif camoufox_proc:
        logger.info(f"Camoufox dahili alt süreci (PID: {camoufox_proc.pid if hasattr(camoufox_proc, 'pid') else 'N/A'}) daha önce kendiliğinden sonlandı, çıkış kodu: {camoufox_proc.poll()}.")
        camoufox_proc = None
    else:
        logger.info("Camoufox dahili alt süreci çalışmıyor veya zaten temizlenmiş.")
    logger.info("--- Temizleme prosedürü tamamlandı (launch_camoufox.py) ---")

atexit.register(cleanup)
def signal_handler(sig, frame):
    logger.info(f"{signal.Signals(sig).name} ({sig}) sinyali alındı. Çıkış prosedürü başlatılıyor...")
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# --- Bağımlılıkları kontrol et (check_dependencies) (dev'den - daha kapsamlı) ---
def check_dependencies():
    logger.info("--- Adım 1: Bağımlılıkları Kontrol Et ---")
    required_modules = {}
    if launch_server is not None and DefaultAddons is not None:
        required_modules["camoufox"] = "camoufox (sunucu ve eklentiler için)"
    elif launch_server is not None:
        required_modules["camoufox_server"] = "camoufox.server"
        logger.warning("  ⚠️ 'camoufox.server' içe aktarıldı, ancak 'camoufox.DefaultAddons' içe aktarılmadı. Eklenti hariç tutma işlevselliği sınırlı olabilir.")
    missing_py_modules = []
    dependencies_ok = True
    if required_modules:
        logger.info("Python modülleri kontrol ediliyor:")
        for module_name, install_package_name in required_modules.items():
            try:
                __import__(module_name)
                logger.info(f"  ✓ Modül '{module_name}' bulundu.")
            except ImportError:
                logger.error(f"  ❌ Modül '{module_name}' (paket: '{install_package_name}') bulunamadı.")
                missing_py_modules.append(install_package_name)
                dependencies_ok = False
    else:
        # Dahili başlatma modu olup olmadığını kontrol et, eğer öyleyse camoufox içe aktarılabilir olmalı
        is_any_internal_arg = any(arg.startswith('--internal-') for arg in sys.argv)
        if is_any_internal_arg and (launch_server is None or DefaultAddons is None):
            logger.error(f"  ❌ Dahili başlatma modu (--internal-*) 'camoufox' paketini gerektiriyor, ancak içe aktarılamadı.")
            dependencies_ok = False
        elif not is_any_internal_arg:
             logger.info("Dahili başlatma modu talep edilmedi ve camoufox.server içe aktarılmadı, 'camoufox' Python paketi kontrolü atlanıyor.")


    try:
        from server import app as server_app_check
        if server_app_check:
             logger.info(f"  ✓ 'app' nesnesi 'server.py' dosyasından başarıyla içe aktarıldı.")
    except ImportError as e_import_server:
        logger.error(f"  ❌ 'app' nesnesi 'server.py' dosyasından içe aktarılamıyor: {e_import_server}")
        logger.error(f"     Lütfen 'server.py' dosyasının var olduğundan ve içe aktarma hatası olmadığından emin olun.")
        dependencies_ok = False

    if not dependencies_ok:
        logger.error("-------------------------------------------------")
        logger.error("❌ Bağımlılık kontrolü başarısız!")
        if missing_py_modules:
            logger.error(f"   Eksik Python kütüphaneleri: {', '.join(missing_py_modules)}")
            logger.error(f"   Lütfen pip kullanarak kurmayı deneyin: pip install {' '.join(missing_py_modules)}")
        logger.error("-------------------------------------------------")
        sys.exit(1)
    else:
        logger.info("✅ Tüm başlatıcı bağımlılık kontrolleri başarılı.")

# --- Port kontrolü ve temizleme fonksiyonları (dev'den - daha sağlam) ---
def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return False
        except OSError:
            return True
        except Exception as e:
            logger.warning(f"Port {port} (host {host}) kontrol edilirken bilinmeyen bir hata oluştu: {e}")
            return True

def find_pids_on_port(port: int) -> list[int]:
    pids = []
    system_platform = platform.system()
    command = ""
    try:
        if system_platform == "Linux" or system_platform == "Darwin":
            command = f"lsof -ti :{port} -sTCP:LISTEN"
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, close_fds=True)
            stdout, stderr = process.communicate(timeout=5)
            if process.returncode == 0 and stdout:
                pids = [int(pid) for pid in stdout.strip().split('\n') if pid.isdigit()]
            elif process.returncode != 0 and ("command not found" in stderr.lower() or "komut bulunamadı" in stderr):
                logger.error(f"'lsof' komutu bulunamadı. Lütfen kurulu olduğundan emin olun.")
            elif process.returncode not in [0, 1]: # lsof bulunamadığında 1 döndürür
                logger.warning(f"lsof komutu çalıştırılamadı (dönüş kodu {process.returncode}): {stderr.strip()}")
        elif system_platform == "Windows":
            command = f'netstat -ano -p TCP | findstr "LISTENING" | findstr ":{port} "'
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(timeout=10)
            if process.returncode == 0 and stdout:
                for line in stdout.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 4 and parts[0].upper() == 'TCP' and f":{port}" in parts[1]:
                        if parts[-1].isdigit(): pids.append(int(parts[-1]))
                pids = list(set(pids)) # yinelenenleri kaldır
            elif process.returncode not in [0, 1]: # findstr bulunamadığında 1 döndürür
                logger.warning(f"netstat/findstr komutu çalıştırılamadı (dönüş kodu {process.returncode}): {stderr.strip()}")
        else:
            logger.warning(f"Portu kullanan işlemleri bulmak için desteklenmeyen işletim sistemi: '{system_platform}'.")
    except FileNotFoundError:
        cmd_name = command.split()[0] if command else "İlgili araç"
        logger.error(f"'{cmd_name}' komutu bulunamadı.")
    except subprocess.TimeoutExpired:
        logger.error(f"'{command}' komutu çalıştırılırken zaman aşımına uğradı.")
    except Exception as e:
        logger.error(f"Port {port} kullanan işlemler aranırken hata oluştu: {e}", exc_info=True)
    return pids

def kill_process_interactive(pid: int) -> bool:
    system_platform = platform.system()
    success = False
    logger.info(f"  PID: {pid} olan süreci sonlandırmaya çalışılıyor...")
    try:
        if system_platform == "Linux" or system_platform == "Darwin":
            result_term = subprocess.run(f"kill {pid}", shell=True, capture_output=True, text=True, timeout=3, check=False)
            if result_term.returncode == 0:
                logger.info(f"    ✓ PID {pid} SIGTERM sinyali gönderildi.")
                success = True
            else:
                logger.warning(f"    PID {pid} SIGTERM başarısız: {result_term.stderr.strip() or result_term.stdout.strip()}. SIGKILL deneniyor...")
                result_kill = subprocess.run(f"kill -9 {pid}", shell=True, capture_output=True, text=True, timeout=3, check=False)
                if result_kill.returncode == 0:
                    logger.info(f"    ✓ PID {pid} SIGKILL sinyali gönderildi.")
                    success = True
                else:
                    logger.error(f"    ✗ PID {pid} SIGKILL başarısız: {result_kill.stderr.strip() or result_kill.stdout.strip()}.")
        elif system_platform == "Windows":
            command_desc = f"taskkill /PID {pid} /T /F"
            result = subprocess.run(command_desc, shell=True, capture_output=True, text=True, timeout=5, check=False)
            output = result.stdout.strip()
            error_output = result.stderr.strip()
            if result.returncode == 0 and ("SUCCESS" in output.upper() or "BAŞARILI" in output):
                logger.info(f"    ✓ PID {pid} taskkill /F ile sonlandırıldı.")
                success = True
            elif "could not find process" in error_output.lower() or "süreç bulunamadı" in error_output: # süreç zaten çıkmış olabilir
                logger.info(f"    PID {pid} taskkill çalıştırılırken bulunamadı (zaten çıkmış olabilir).")
                success = True # hedef portun kullanılabilir olması olduğu için başarılı sayılır
            else:
                logger.error(f"    ✗ PID {pid} taskkill /F başarısız: {(error_output + ' ' + output).strip()}.")
        else:
            logger.warning(f"    Süreci sonlandırmak için desteklenmeyen işletim sistemi: '{system_platform}'.")
    except Exception as e:
        logger.error(f"    PID {pid} sonlandırılırken beklenmeyen bir hata oluştu: {e}", exc_info=True)
    return success

# --- Zaman aşımlı kullanıcı girişi fonksiyonu (dev'den - daha sağlam Windows uygulaması) ---
def input_with_timeout(prompt_message: str, timeout_seconds: int = 30) -> str:
    print(prompt_message, end='', flush=True)
    if sys.platform == "win32":
        user_input_container = [None]
        def get_input_in_thread():
            try:
                user_input_container[0] = sys.stdin.readline().strip()
            except Exception:
                user_input_container[0] = "" # hata durumunda boş dize döndür
        input_thread = threading.Thread(target=get_input_in_thread, daemon=True)
        input_thread.start()
        input_thread.join(timeout=timeout_seconds)
        if input_thread.is_alive():
            print("\nGiriş zaman aşımına uğradı. Varsayılan değer kullanılacak.", flush=True)
            return ""
        return user_input_container[0] if user_input_container[0] is not None else ""
    else: # Linux/macOS
        readable_fds, _, _ = select.select([sys.stdin], [], [], timeout_seconds)
        if readable_fds:
            return sys.stdin.readline().strip()
        else:
            print("\nGiriş zaman aşımına uğradı. Varsayılan değer kullanılacak.", flush=True)
            return ""

def get_proxy_from_gsettings():
    """
    Retrieves the proxy settings from GSettings on Linux systems.
    Returns a proxy string like "http://host:port" or None.
    """
    def _run_gsettings_command(command_parts: list[str]) -> str | None:
        """Helper function to run gsettings command and return cleaned string output."""
        try:
            process_result = subprocess.run(
                command_parts,
                capture_output=True,
                text=True,
                check=False, # Do not raise CalledProcessError for non-zero exit codes
                timeout=1  # Timeout for the subprocess call
            )
            if process_result.returncode == 0:
                value = process_result.stdout.strip()
                if value.startswith("'") and value.endswith("'"): # Remove surrounding single quotes
                    value = value[1:-1]

                # If after stripping quotes, value is empty, or it's a gsettings "empty" representation
                if not value or value == "''" or value == "@as []" or value == "[]":
                    return None
                return value
            else:
                return None
        except subprocess.TimeoutExpired:
            return None
        except Exception: # Broad exception as per pseudocode
            return None

    proxy_mode = _run_gsettings_command(["gsettings", "get", "org.gnome.system.proxy", "mode"])

    if proxy_mode == "manual":
        # Try HTTP proxy first
        http_host = _run_gsettings_command(["gsettings", "get", "org.gnome.system.proxy.http", "host"])
        http_port_str = _run_gsettings_command(["gsettings", "get", "org.gnome.system.proxy.http", "port"])

        if http_host and http_port_str:
            try:
                http_port = int(http_port_str)
                if http_port > 0:
                    return f"http://{http_host}:{http_port}"
            except ValueError:
                pass  # Continue to HTTPS

        # Try HTTPS proxy if HTTP not found or invalid
        https_host = _run_gsettings_command(["gsettings", "get", "org.gnome.system.proxy.https", "host"])
        https_port_str = _run_gsettings_command(["gsettings", "get", "org.gnome.system.proxy.https", "port"])

        if https_host and https_port_str:
            try:
                https_port = int(https_port_str)
                if https_port > 0:
                    # Note: Even for HTTPS proxy settings, the scheme for Playwright/requests is usually http://
                    return f"http://{https_host}:{https_port}"
            except ValueError:
                pass

    return None


def determine_proxy_configuration(internal_camoufox_proxy_arg=None):
    """
    Birleşik proxy yapılandırması belirleme fonksiyonu
    Öncelik sırası: Komut satırı argümanları > Ortam değişkenleri > Sistem ayarları

    Args:
        internal_camoufox_proxy_arg: --internal-camoufox-proxy komut satırı argüman değeri

    Returns:
        dict: Proxy yapılandırma bilgilerini içeren sözlük
        {
            'camoufox_proxy': str or None,  # Camoufox tarayıcısı tarafından kullanılan proxy
            'stream_proxy': str or None,    # Akış proxy hizmeti tarafından kullanılan üst akış proxy
            'source': str                   # Proxy kaynağı açıklaması
        }
    """
    result = {
        'camoufox_proxy': None,
        'stream_proxy': None,
        'source': 'Proxy yok'
    }

    # 1. Komut satırı argümanlarını öncelikli kullan
    if internal_camoufox_proxy_arg is not None:
        if internal_camoufox_proxy_arg.strip():  # Boş olmayan dize
            result['camoufox_proxy'] = internal_camoufox_proxy_arg.strip()
            result['stream_proxy'] = internal_camoufox_proxy_arg.strip()
            result['source'] = f"Komut satırı argümanı --internal-camoufox-proxy: {internal_camoufox_proxy_arg.strip()}"
        else:  # Boş dize, proxy kullanımını açıkça devre dışı bırak
            result['source'] = "Komut satırı argümanı --internal-camoufox-proxy='' (proxy kullanımını açıkça devre dışı bırak)"
        return result

    # 2. Ortam değişkeni UNIFIED_PROXY_CONFIG'ı dene (HTTP_PROXY/HTTPS_PROXY'dan daha yüksek öncelikli)
    unified_proxy = os.environ.get("UNIFIED_PROXY_CONFIG")
    if unified_proxy:
        result['camoufox_proxy'] = unified_proxy
        result['stream_proxy'] = unified_proxy
        result['source'] = f"Ortam değişkeni UNIFIED_PROXY_CONFIG: {unified_proxy}"
        return result

    # 3. Ortam değişkeni HTTP_PROXY'yi dene
    http_proxy = os.environ.get("HTTP_PROXY")
    if http_proxy:
        result['camoufox_proxy'] = http_proxy
        result['stream_proxy'] = http_proxy
        result['source'] = f"Ortam değişkeni HTTP_PROXY: {http_proxy}"
        return result

    # 4. Ortam değişkeni HTTPS_PROXY'yi dene
    https_proxy = os.environ.get("HTTPS_PROXY")
    if https_proxy:
        result['camoufox_proxy'] = https_proxy
        result['stream_proxy'] = https_proxy
        result['source'] = f"Ortam değişkeni HTTPS_PROXY: {https_proxy}"
        return result

    # 5. Sistem proxy ayarlarını dene (sadece Linux için)
    if sys.platform.startswith('linux'):
        gsettings_proxy = get_proxy_from_gsettings()
        if gsettings_proxy:
            result['camoufox_proxy'] = gsettings_proxy
            result['stream_proxy'] = gsettings_proxy
            result['source'] = f"gsettings sistem proxy'si: {gsettings_proxy}"
            return result

    return result


# --- Ana yürütme mantığı ---
if __name__ == "__main__":
    # Dahili başlatma çağrısı olup olmadığını kontrol et, öyleyse başlatıcının günlüğünü yapılandırma
    is_internal_call = any(arg.startswith('--internal-') for arg in sys.argv)
    if not is_internal_call:
        setup_launcher_logging(log_level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Camoufox tarayıcı simülasyonu ve FastAPI proxy sunucusunun başlatıcısı.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # Dahili parametreler (dev'den)
    parser.add_argument('--internal-launch-mode', type=str, choices=['debug', 'headless', 'virtual_headless'], help=argparse.SUPPRESS)
    parser.add_argument('--internal-auth-file', type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument('--internal-camoufox-port', type=int, default=DEFAULT_CAMOUFOX_PORT, help=argparse.SUPPRESS)
    parser.add_argument('--internal-camoufox-proxy', type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument('--internal-camoufox-os', type=str, default="random", help=argparse.SUPPRESS)


    # Kullanıcı tarafından görülebilir parametreler (dev ve helper'dan birleştirildi)
    parser.add_argument("--server-port", type=int, default=DEFAULT_SERVER_PORT, help=f"FastAPI sunucunun dinlediği port (varsayılan: {DEFAULT_SERVER_PORT})")
    parser.add_argument(
        "--stream-port",
        type=int,
        default=DEFAULT_STREAM_PORT, # .env dosyasından varsayılan değeri oku
        help=(
            f"Akış proxy sunucusunun kullandığı port"
            f"Bu özelliği devre dışı bırakmak için --stream-port=0 kullanın . Varsayılan: {DEFAULT_STREAM_PORT}"
        )
    )
    parser.add_argument(
        "--helper",
        type=str,
        default=DEFAULT_HELPER_ENDPOINT, # Varsayılan değeri kullan
        help=(
            f"Helper sunucusunun getStreamResponse uç noktası adresi (örneğin: http://127.0.1:3121/getStreamResponse). "
            f"Bu özelliği devre dışı bırakmak için boş dize sağlayın (örneğin: --helper=''). Varsayılan: {DEFAULT_HELPER_ENDPOINT}"
        )
    )
    parser.add_argument(
        "--camoufox-debug-port", # dev'den
        type=int,
        default=DEFAULT_CAMOUFOX_PORT,
        help=f"Dahili Camoufox örneğinin dinlediği hata ayıklama portu (varsayılan: {DEFAULT_CAMOUFOX_PORT})"
    )
    mode_selection_group = parser.add_mutually_exclusive_group() # dev'den (daha fazla seçenek)
    mode_selection_group.add_argument("--debug", action="store_true", help="Hata ayıklama modunu başlat (tarayıcı arayüzü görünebilir, etkileşimli kimlik doğrulamaya izin verir)")
    mode_selection_group.add_argument("--headless", action="store_true", help="Başsız modu başlat (tarayıcı arayüzü yok, önceden kaydedilmiş kimlik doğrulama dosyaları gerekir)")
    mode_selection_group.add_argument("--virtual-display", action="store_true", help="Başsız modu başlat ve sanal ekran kullan (Xvfb, sadece Linux için)") # dev'den

    # --camoufox-os parametresi kaldırıldı, komut dosyası içinde sistem otomatik olarak algılanacak ve ayarlanacak
    parser.add_argument( # dev'den
        "--active-auth-json", type=str, default=None,
        help="[Başsız mod/hata ayıklama modu isteğe bağlı] Kullanılacak etkin kimlik doğrulama JSON dosyasının yolunu belirtin (auth_profiles/active/ veya auth_profiles/saved/ içinde veya mutlak yol)."
             "Sağlanmazsa, başsız mod etkin dizinindeki en son JSON dosyasını kullanır, hata ayıklama modu seçim yapar veya kullanmaz."
    )
    parser.add_argument( # dev'den
        "--auto-save-auth", action='store_true',
        help="[Hata ayıklama modu] Giriş başarılı olduktan sonra, daha önce kimlik doğrulama dosyası yüklenmediyse, yeni kimlik doğrulama durumunu otomatik olarak istem ve kaydet."
    )
    parser.add_argument(
        "--save-auth-as", type=str, default=None,
        help="[Hata ayıklama modu] Yeni kimlik doğrulama dosyasını kaydetmek için dosya adını belirtin (.json uzantısı olmadan)."
    )
    parser.add_argument( # dev'den
        "--auth-save-timeout", type=int, default=DEFAULT_AUTH_SAVE_TIMEOUT,
        help=f"[Hata ayıklama modu] Kimlik doğrulamayı otomatik kaydetmek veya kimlik doğrulama dosyası adı girmek için bekleme zaman aşımı (saniye). Varsayılan: {DEFAULT_AUTH_SAVE_TIMEOUT}"
    )
    parser.add_argument(
        "--exit-on-auth-save", action='store_true',
        help="[Hata ayıklama modu] Yeni kimlik doğrulama dosyasını UI aracılığıyla başarıyla kaydettikten sonra, başlatıcıyı ve tüm ilgili süreçleri otomatik olarak kapatın."
    )
    # Günlükleme ile ilgili parametreler (dev'den)
    parser.add_argument(
        "--server-log-level", type=str, default=DEFAULT_SERVER_LOG_LEVEL, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=f"server.py için günlük seviyesi. Varsayılan: {DEFAULT_SERVER_LOG_LEVEL}"
    )
    parser.add_argument(
        "--server-redirect-print", action='store_true',
        help="server.py içindeki print çıktılarını günlük sistemine yönlendirin. input() istemlerinin hata ayıklama modunda görünür olması için varsayılan olarak yönlendirilmez."
    )
    parser.add_argument("--debug-logs", action='store_true', help="server.py içindeki DEBUG seviyesi ayrıntılı günlükleri etkinleştirin (ortam değişkeni DEBUG_LOGS_ENABLED).")
    parser.add_argument("--trace-logs", action='store_true', help="server.py içindeki TRACE seviyesi daha ayrıntılı günlükleri etkinleştirin (ortam değişkeni TRACE_LOGS_ENABLED).")

    args = parser.parse_args()

    if not ENABLE_QWEN_LOGIN_SUPPORT:
        if args.active_auth_json:
            logger.warning("ENABLE_QWEN_LOGIN_SUPPORT is disabled; ignoring --active-auth-json.")
        if args.auto_save_auth:
            logger.warning("ENABLE_QWEN_LOGIN_SUPPORT is disabled; ignoring --auto-save-auth.")
        if args.save_auth_as:
            logger.warning("ENABLE_QWEN_LOGIN_SUPPORT is disabled; ignoring --save-auth-as.")
        args.active_auth_json = None
        args.auto_save_auth = False
        args.save_auth_as = None

    # --- Geçerli sistemi otomatik algıla ve Camoufox OS simülasyonunu ayarla ---
    # Bu değişken, sonraki Camoufox dahili başlatma ve HOST_OS_FOR_SHORTCUT ayarı için kullanılacak
    current_system_for_camoufox = platform.system()
    if current_system_for_camoufox == "Linux":
        simulated_os_for_camoufox = "linux"
    elif current_system_for_camoufox == "Windows":
        simulated_os_for_camoufox = "windows"
    elif current_system_for_camoufox == "Darwin": # macOS
        simulated_os_for_camoufox = "macos"
    else:
        simulated_os_for_camoufox = "linux" # Bilinmeyen sistem için varsayılan geri dönüş
        logger.warning(f"Geçerli sistem '{current_system_for_camoufox}' tanınmıyor. Camoufox OS simülasyonu varsayılan olarak ayarlanacak: {simulated_os_for_camoufox}")
    logger.info(f"Geçerli sistem '{current_system_for_camoufox}'e göre Camoufox OS simülasyonu otomatik olarak ayarlandı: {simulated_os_for_camoufox}")

    # --- Dahili Camoufox başlatma mantığını işle (komut dosyası kendisini alt işlem olarak çağırıyorsa) (dev'den) ---
    if args.internal_launch_mode:
        if not launch_server or not DefaultAddons:
            print("❌ Kritik Hata (--internal-launch-mode): camoufox.server.launch_server veya camoufox.DefaultAddons kullanılamıyor. Komut dosyası devam edemiyor.", file=sys.stderr)
            sys.exit(1)

        internal_mode_arg = args.internal_launch_mode
        auth_file = args.internal_auth_file
        camoufox_port_internal = args.internal_camoufox_port
        # Birleşik proxy yapılandırması belirleme mantığını kullan
        proxy_config = determine_proxy_configuration(args.internal_camoufox_proxy)
        actual_proxy_to_use = proxy_config['camoufox_proxy']
        print(f"--- [Dahili Camoufox Başlatma] Proxy yapılandırması: {proxy_config['source']} ---", flush=True)

        camoufox_proxy_internal = actual_proxy_to_use # Daha sonraki kullanım için bu değişkeni güncelle
        camoufox_os_internal = args.internal_camoufox_os


        print(f"--- [Dahili Camoufox Başlatma] Mod: {internal_mode_arg}, Kimlik doğrulama dosyası: {os.path.basename(auth_file) if auth_file else 'Yok'}, "
              f"Camoufox portu: {camoufox_port_internal}, Proxy: {camoufox_proxy_internal or 'Yok'}, Simüle edilen OS: {camoufox_os_internal} ---", flush=True)
        print(f"--- [Dahili Camoufox Başlatma] camoufox.server.launch_server çağrısı yapılıyor ... ---", flush=True)

        try:
            launch_args_for_internal_camoufox = {
                "port": camoufox_port_internal,
                "addons": [],
                # "proxy": camoufox_proxy_internal, # Kaldırıldı
                "exclude_addons": [DefaultAddons.UBO], # DefaultAddons.UBO'nun mevcut olduğunu varsay
                "window": (1440, 900)
            }

            # Proxy'yi doğru ekleme yolu
            if camoufox_proxy_internal: # Eğer proxy dizesi varsa ve boş değilse
                launch_args_for_internal_camoufox["proxy"] = {"server": camoufox_proxy_internal}
            # Eğer camoufox_proxy_internal None veya boş dize ise, "proxy" anahtarı eklenmez.
            if auth_file:
                launch_args_for_internal_camoufox["storage_state"] = auth_file

            if "," in camoufox_os_internal:
                camoufox_os_list_internal = [s.strip().lower() for s in camoufox_os_internal.split(',')]
                valid_os_values = ["windows", "macos", "linux"]
                if not all(val in valid_os_values for val in camoufox_os_list_internal):
                    print(f"❌ Dahili Camoufox başlatma hatası: camoufox_os_internal listesi geçersiz değerler içeriyor: {camoufox_os_list_internal}", file=sys.stderr)
                    sys.exit(1)
                launch_args_for_internal_camoufox['os'] = camoufox_os_list_internal
            elif camoufox_os_internal.lower() in ["windows", "macos", "linux"]:
                launch_args_for_internal_camoufox['os'] = camoufox_os_internal.lower()
            elif camoufox_os_internal.lower() != "random":
                print(f"❌ Dahili Camoufox başlatma hatası: camoufox_os_internal değeri geçersiz: '{camoufox_os_internal}'", file=sys.stderr)
                sys.exit(1)

            print(f"  launch_server'a aktarılan parametreler: {launch_args_for_internal_camoufox}", flush=True)

            if internal_mode_arg == 'headless':
                launch_server(headless=True, **launch_args_for_internal_camoufox)
            elif internal_mode_arg == 'virtual_headless':
                launch_server(headless="virtual", **launch_args_for_internal_camoufox)
            elif internal_mode_arg == 'debug':
                launch_server(headless=False, **launch_args_for_internal_camoufox)

            print(f"--- [Dahili Camoufox Başlatma] camoufox.server.launch_server ({internal_mode_arg} modu) çağrısı tamamlandı/engellendi. Komut dosyası sonlanmasını bekleyecek. ---", flush=True)
        except Exception as e_internal_launch_final:
            print(f"❌ Hata (--internal-launch-mode): camoufox.server.launch_server çalıştırılırken istisna oluştu: {e_internal_launch_final}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # --- Ana başlatıcı mantığı ---
    logger.info("🚀 Camoufox Başlatıcı Çalışmaya Başladı 🚀")
    logger.info("=================================================")
    ensure_auth_dirs_exist()
    check_dependencies()
    logger.info("=================================================")

    deprecated_auth_state_path = os.path.join(os.path.dirname(__file__), "auth_state.json")
    if os.path.exists(deprecated_auth_state_path):
        logger.warning(f"Kullanımdan kaldırılmış kimlik doğrulama dosyası tespit edildi: {deprecated_auth_state_path}. Bu dosya artık doğrudan kullanılmıyor.")
        logger.warning("Yeni kimlik doğrulama dosyalarını oluşturmak için hata ayıklama modunu kullanın ve 'auth_profiles' dizinindeki dosyaları ihtiyaca göre yönetin.")

    final_launch_mode = None # dev'den
    if args.debug:
        final_launch_mode = 'debug'
    elif args.headless:
        final_launch_mode = 'headless'
    elif args.virtual_display: # dev'den
        final_launch_mode = 'virtual_headless'
        if platform.system() != "Linux":
            logger.warning("⚠️ --virtual-display modu öncelikle Linux için tasarlanmıştır. Linux dışı sistemlerde, davranış standart başsız mod gibi olabilir veya Camoufox dahili hatalara neden olabilir.")
    else:
        # Varsayılan olarak .env dosyasındaki LAUNCH_MODE yapılandırmasını oku
        env_launch_mode = os.environ.get('LAUNCH_MODE', '').lower()
        default_mode_from_env = None
        default_interactive_choice = '1' # Varsayılan olarak başsız modu seç

        # .env'deki LAUNCH_MODE değerini etkileşimli seçimle eşle
        if env_launch_mode == 'headless':
            default_mode_from_env = 'headless'
            default_interactive_choice = '1'
        elif env_launch_mode == 'debug' or env_launch_mode == 'normal':
            default_mode_from_env = 'debug'
            default_interactive_choice = '2'
        elif env_launch_mode == 'virtual_display' or env_launch_mode == 'virtual_headless':
            default_mode_from_env = 'virtual_headless'
            default_interactive_choice = '3' if platform.system() == "Linux" else '1'

        logger.info("--- Lütfen başlatma modu seçin (komut satırı argümanı ile belirtilmemişse) ---")
        if env_launch_mode and default_mode_from_env:
            logger.info(f"  .env dosyasından varsayılan başlatma modu okundu: {env_launch_mode} -> {default_mode_from_env}")

        prompt_options_text = "[1] Başsız mod, [2] Hata ayıklama modu"
        valid_choices = {'1': 'headless', '2': 'debug'}

        if platform.system() == "Linux": # dev'den
            prompt_options_text += ", [3] Başsız mod (sanal ekran Xvfb)"
            valid_choices['3'] = 'virtual_headless'

        # Mevcut varsayılan seçimi gösteren istemi oluştur
        default_mode_name = valid_choices.get(default_interactive_choice, 'headless')
        user_mode_choice = input_with_timeout(
            f"  Lütfen başlatma modunu girin ({prompt_options_text}; Varsayılan: {default_interactive_choice} {default_mode_name} modu, {15} saniye zaman aşımı): ", 15
        ) or default_interactive_choice

        if user_mode_choice in valid_choices:
            final_launch_mode = valid_choices[user_mode_choice]
        else:
            final_launch_mode = default_mode_from_env or 'headless' # .env varsayılanını kullan veya başsız moda geri dön
            logger.info(f"Geçersiz giriş '{user_mode_choice}' veya zaman aşımı, varsayılan başlatma modu kullanılıyor: {final_launch_mode} modu")
    logger.info(f"Son olarak seçilen başlatma modu: {final_launch_mode.replace('_', ' ')} modu")
    logger.info("-------------------------------------------------")

    effective_active_auth_json_path = None # Önceden başlat

    if ENABLE_QWEN_LOGIN_SUPPORT:
        # --- Etkileşimli kimlik doğrulama dosyası oluşturma mantığı ---
        if final_launch_mode == 'debug' and not args.active_auth_json:
            create_new_auth_choice = input_with_timeout(
                "  Yeni bir kimlik doğrulama dosyası oluşturmak ve kaydetmek ister misiniz? (e/h; Varsayılan: h, 15s zaman aşımı): ", 15
            ).strip().lower()
            if create_new_auth_choice == 'y':
                new_auth_filename = ""
                while not new_auth_filename:
                    new_auth_filename_input = input_with_timeout(
                        f"  Lütfen kaydedilecek dosya adını girin (.json uzantısı olmadan, harf/sayı/-/_): ", args.auth_save_timeout
                    ).strip()
                    # Basit geçerlilik kontrolü
                    if re.match(r"^[a-zA-Z0-9_-]+$", new_auth_filename_input):
                        new_auth_filename = new_auth_filename_input
                    elif new_auth_filename_input == "":
                        logger.info("Giriş boş veya zaman aşımına uğradı, yeni kimlik doğrulama dosyası oluşturma iptal ediliyor.")
                        break
                    else:
                        print("  Dosya adı geçersiz karakterler içeriyor, lütfen tekrar deneyin.")

                if new_auth_filename:
                    args.auto_save_auth = True
                    args.save_auth_as = new_auth_filename
                    logger.info(f"  Pekala, giriş başarılı olduktan sonra kimlik doğrulama dosyası otomatik olarak şu şekilde kaydedilecek: {new_auth_filename}.json")
                    # Bu modda, mevcut kimlik doğrulama dosyalarının hiçbiri yüklenmemelidir
                    if effective_active_auth_json_path:
                        logger.info("  Yeni kimlik doğrulama dosyası oluşturulacağı için önceki kimlik doğrulama dosyası ayarları temizlendi.")
                        effective_active_auth_json_path = None
            else:
                logger.info("  Pekala, yeni kimlik doğrulama dosyası oluşturulmayacak.")
    else:
        logger.info("ENABLE_QWEN_LOGIN_SUPPORT devre dışı; kimlik doğrulama profili istemleri atlanıyor.")

    if final_launch_mode == 'virtual_headless' and platform.system() == "Linux": # dev'den
        logger.info("--- Xvfb (sanal ekran) bağımlılığı kontrol ediliyor ---")
        if not shutil.which("Xvfb"):
            logger.error("  ❌ Xvfb bulunamadı. Sanal ekran modu Xvfb gerektiriyor. Lütfen kurun (örneğin: sudo apt-get install xvfb) ve tekrar deneyin.")
            sys.exit(1)
        logger.info(" ✓ Xvfb bulundu.")

    server_target_port = args.server_port
    logger.info(f"--- Adım 2: FastAPI sunucu hedef portunun ({server_target_port}) kullanımda olup olmadığını kontrol et ---")
    port_is_available = False
    uvicorn_bind_host = "0.0.0.0" # dev'den (yardımcıda 127.0.0.1 idi)
    if is_port_in_use(server_target_port, host=uvicorn_bind_host):
        logger.warning(f"  ❌ Port {server_target_port} (host {uvicorn_bind_host}) şu anda kullanımda.")
        pids_on_port = find_pids_on_port(server_target_port)
        if pids_on_port:
            logger.warning(f"     Aşağıdaki PID'lerin portu kullanması olası: {server_target_port}: {pids_on_port}")
            if final_launch_mode == 'debug':
                sys.stderr.flush()
                # Tutarlılık için input_with_timeout kullan, ancak burada zaman aşımı kesin olarak gerekli olmayabilir
                choice = input_with_timeout(f"     Bu süreçleri sonlandırmayı denemek ister misiniz? (e/h, h girişi devam edecek ve başlatma başarısız olabilir, 15s zaman aşımı): ", 15).strip().lower()
                if choice == 'y':
                    logger.info("     Kullanıcı süreçleri sonlandırmayı denemeyi seçti...")
                    all_killed = all(kill_process_interactive(pid) for pid in pids_on_port)
                    time.sleep(2)
                    if not is_port_in_use(server_target_port, host=uvicorn_bind_host):
                        logger.info(f"     ✅ Port {server_target_port} (host {uvicorn_bind_host}) artık kullanılabilir.")
                        port_is_available = True
                    else:
                        logger.error(f"     ❌ Sonlandırmayı denedikten sonra port {server_target_port} (host {uvicorn_bind_host}) hala kullanımda.")
                else:
                    logger.info("     Kullanıcı otomatik sonlandırmayı reddetti veya zaman aşımına uğradı. Sunucu başlatılmaya devam edilecek.")
            else:
                 logger.error(f"     Başsız modda, portu kullanan süreçleri otomatik sonlandırmaya çalışılmaz. Sunucu başlatması başarısız olabilir.")
        else:
            logger.warning(f"     Portu kullanan süreçler otomatik olarak tanımlanamadı {server_target_port}. Sunucu başlatması başarısız olabilir.")

        if not port_is_available:
            logger.warning(f"--- Port {server_target_port} hala kullanımda olabilir. Sunucu başlatmaya devam ediliyor, port bağlama işlemini kendi halledecek. ---")
    else:
        logger.info(f"  ✅ Port {server_target_port} (host {uvicorn_bind_host}) şu anda kullanılabilir.")
        port_is_available = True


    logger.info("--- Adım 3: Camoufox dahili sürecini hazırla ve başlat ---")
    captured_ws_endpoint = None
    # effective_active_auth_json_path = None # dev'den # Önceden yapıldı

    if ENABLE_QWEN_LOGIN_SUPPORT:
        if args.active_auth_json:
            logger.info(f"  --active-auth-json argümanı tarafından sağlanan yolu deniyor: '{args.active_auth_json}'")
            candidate_path = os.path.expanduser(args.active_auth_json)

            # Yolu çözümlemeyi dene:
            # 1. Mutlak yol olarak
            if os.path.isabs(candidate_path) and os.path.exists(candidate_path) and os.path.isfile(candidate_path):
                effective_active_auth_json_path = candidate_path
            else:
                # 2. Geçerli çalışma dizinine göre göreli yol olarak
                path_rel_to_cwd = os.path.abspath(candidate_path)
                if os.path.exists(path_rel_to_cwd) and os.path.isfile(path_rel_to_cwd):
                    effective_active_auth_json_path = path_rel_to_cwd
                else:
                    # 3. Komut dosyası dizinine göre göreli yol olarak
                    path_rel_to_script = os.path.join(os.path.dirname(__file__), candidate_path)
                    if os.path.exists(path_rel_to_script) and os.path.isfile(path_rel_to_script):
                        effective_active_auth_json_path = path_rel_to_script
                    # 4. Sadece bir dosya adıysa, ACTIVE_AUTH_DIR ve ardından SAVED_AUTH_DIR içinde kontrol et
                    elif not os.path.sep in candidate_path: # Bu sadece bir dosya adıdır
                        path_in_active = os.path.join(ACTIVE_AUTH_DIR, candidate_path)
                        if os.path.exists(path_in_active) and os.path.isfile(path_in_active):
                            effective_active_auth_json_path = path_in_active
                        else:
                            path_in_saved = os.path.join(SAVED_AUTH_DIR, candidate_path)
                            if os.path.exists(path_in_saved) and os.path.isfile(path_in_saved):
                                effective_active_auth_json_path = path_in_saved

            if effective_active_auth_json_path:
                logger.info(f"  --active-auth-json tarafından çözümlenen kimlik doğrulama dosyası kullanılacak: {effective_active_auth_json_path}")
            else:
                logger.error(f"❌ Belirtilen kimlik doğrulama dosyası (--active-auth-json='{args.active_auth_json}') bulunamadı veya bir dosya değil.")
                sys.exit(1)
        else:
            # --active-auth-json sağlanmadı.
            if final_launch_mode == 'debug':
                # Hata ayıklama modu için, tüm dizini tarayın ve kullanıcıya kullanılabilir kimlik doğrulama dosyalarından seçim yapın, otomatik olarak hiçbir dosya kullanmayın
                logger.info(f"  Hata ayıklama modu: Tüm dizini tarayın ve kullanıcıya kullanılabilir kimlik doğrulama dosyalarından seçim yapın...")
            else:
                # Başsız mod için, active/ dizinindeki varsayılan kimlik doğrulama dosyasını kontrol edin
                logger.info(f"  --active-auth-json sağlanmadı. '{ACTIVE_AUTH_DIR}' içindeki varsayılan kimlik doğrulama dosyasını kontrol ediyor...")
                try:
                    if os.path.exists(ACTIVE_AUTH_DIR):
                        active_json_files = sorted([
                            f for f in os.listdir(ACTIVE_AUTH_DIR)
                            if f.lower().endswith('.json') and os.path.isfile(os.path.join(ACTIVE_AUTH_DIR, f))
                        ])
                        if active_json_files:
                            effective_active_auth_json_path = os.path.join(ACTIVE_AUTH_DIR, active_json_files[0])
                            logger.info(f"  '{ACTIVE_AUTH_DIR}' içinde isme göre sıralanmış ilk JSON dosyası kullanılacak: {os.path.basename(effective_active_auth_json_path)}")
                        else:
                            logger.info(f"  Dizin '{ACTIVE_AUTH_DIR}' boş veya JSON dosyaları içermiyor.")
                    else:
                        logger.info(f"  Dizin '{ACTIVE_AUTH_DIR}' mevcut değil.")
                except Exception as e_scan_active:
                    logger.warning(f"  '{ACTIVE_AUTH_DIR}' taranırken hata oluştu: {e_scan_active}", exc_info=True)

            # Hata ayıklama modu kullanıcı seçim mantığını işle
            if final_launch_mode == 'debug' and not args.auto_save_auth:
                # Hata ayıklama modu için, tüm dizini tarayın ve kullanıcıya seçim yaptırın
                available_profiles = []
                # Önce ACTIVE_AUTH_DIR, sonra SAVED_AUTH_DIR tarayın
                for profile_dir_path_str, dir_label in [(ACTIVE_AUTH_DIR, "active"), (SAVED_AUTH_DIR, "saved")]:
                    if os.path.exists(profile_dir_path_str):
                        try:
                            # Her dizinde dosya isimlerini sıralayın
                            filenames = sorted([
                                f for f in os.listdir(profile_dir_path_str)
                                if f.lower().endswith(".json") and os.path.isfile(os.path.join(profile_dir_path_str, f))
                            ])
                            for filename in filenames:
                                full_path = os.path.join(profile_dir_path_str, filename)
                                available_profiles.append({"name": f"{dir_label}/{filename}", "path": full_path})
                        except OSError as e:
                            logger.warning(f"   ⚠️ Uyarı: '{profile_dir_path_str}' dizini okunamıyor: {e}")

                if available_profiles:
                    # Kullanılabilir profil listesini sıralayın, tutarlı bir gösterim sırası için
                    available_profiles.sort(key=lambda x: x['name'])
                    print('-'*60 + "\n   Aşağıdaki kullanılabilir kimlik doğrulama dosyaları bulundu:", flush=True)
                    for i, profile in enumerate(available_profiles): print(f"     {i+1}: {profile['name']}", flush=True)
                    print("     N: Hiçbir dosya yükleme (tarayıcının mevcut durumunu kullan)\n" + '-'*60, flush=True)
                    choice = input_with_timeout(f"   Lütfen yüklenecek kimlik doğrulama dosyası numarasını seçin (N girin veya doğrudan Enter tuşuna basın, {args.auth_save_timeout}s zaman aşımı): ", args.auth_save_timeout)
                    if choice.strip().lower() not in ['n', '']:
                        try:
                            choice_index = int(choice.strip()) - 1
                            if 0 <= choice_index < len(available_profiles):
                                selected_profile = available_profiles[choice_index]
                                effective_active_auth_json_path = selected_profile["path"]
                                logger.info(f"   Kimlik doğrulama dosyası yüklendi: {selected_profile['name']}")
                                print(f"   Seçilen yükleme: {selected_profile['name']}", flush=True)
                            else:
                                logger.info("   Geçersiz seçim numarası veya zaman aşımı. Kimlik doğrulama dosyası yüklenmeyecek.")
                                print("   Geçersiz seçim numarası veya zaman aşımı. Kimlik doğrulama dosyası yüklenmeyecek.", flush=True)
                        except ValueError:
                            logger.info("   Geçersiz giriş. Kimlik doğrulama dosyası yüklenmeyecek.")
                            print("   Geçersiz giriş. Kimlik doğrulama dosyası yüklenmeyecek.", flush=True)
                    else:
                        logger.info("   Pekala, kimlik doğrulama dosyası yüklenmeyecek veya zaman aşımına uğradı.", flush=True)
                        print("   Pekala, kimlik doğrulama dosyası yüklenmeyecek veya zaman aşımına uğradı.", flush=True)
                    print('-'*60, flush=True)
                else:
                    logger.info("   Kimlik doğrulama dosyası bulunamadı. Tarayıcının mevcut durumu kullanılacak.", flush=True)
                    print("   Kimlik doğrulama dosyası bulunamadı. Tarayıcının mevcut durumu kullanılacak.", flush=True)
            elif not effective_active_auth_json_path and not args.auto_save_auth:
                # Başsız mod için, --active-auth-json sağlanmadıysa ve active/ boşsa hata ver
                logger.error(f"  ❌ {final_launch_mode} mod hatası: --active-auth-json sağlanmadı ve etkin kimlik doğrulama dizininde '{ACTIVE_AUTH_DIR}' '.json' kimlik doğrulama dosyası bulunamadı. Lütfen önce hata ayıklama modunda bir tane kaydedin veya argümanla belirtin.")
                sys.exit(1)
    else:
        logger.info("ENABLE_QWEN_LOGIN_SUPPORT devre dışı; kimlik doğrulama profilleri Qwen için göz ardı ediliyor.")

    # Camoufox dahili başlatma komutunu oluştur (dev'den)
    camoufox_internal_cmd_args = [
        PYTHON_EXECUTABLE, '-u', __file__,
        '--internal-launch-mode', final_launch_mode
    ]
    if effective_active_auth_json_path:
        camoufox_internal_cmd_args.extend(['--internal-auth-file', effective_active_auth_json_path])

    camoufox_internal_cmd_args.extend(['--internal-camoufox-os', simulated_os_for_camoufox])
    camoufox_internal_cmd_args.extend(['--internal-camoufox-port', str(args.camoufox_debug_port)])

    # Düzeltme: Proxy parametresini dahili Camoufox sürecine aktar
    if args.internal_camoufox_proxy is not None:
        camoufox_internal_cmd_args.extend(['--internal-camoufox-proxy', args.internal_camoufox_proxy])

    camoufox_popen_kwargs = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE, 'env': os.environ.copy()}
    camoufox_popen_kwargs['env']['PYTHONIOENCODING'] = 'utf-8'
    if sys.platform != "win32" and final_launch_mode != 'debug':
        camoufox_popen_kwargs['start_new_session'] = True
    elif sys.platform == "win32" and (final_launch_mode == 'headless' or final_launch_mode == 'virtual_headless'):
         camoufox_popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW


    try:
        logger.info(f"  Camoufox dahili başlatma komutu çalıştırılacak: {' '.join(camoufox_internal_cmd_args)}")
        camoufox_proc = subprocess.Popen(camoufox_internal_cmd_args, **camoufox_popen_kwargs)
        logger.info(f" Camoufox dahili süreci başlatıldı (PID: {camoufox_proc.pid}). WebSocket uç noktası çıktısı bekleniyor (en fazla {ENDPOINT_CAPTURE_TIMEOUT} saniye)...")

        camoufox_output_q = queue.Queue()
        camoufox_stdout_reader = threading.Thread(target=_enqueue_output, args=(camoufox_proc.stdout, "stdout", camoufox_output_q, camoufox_proc.pid), daemon=True)
        camoufox_stderr_reader = threading.Thread(target=_enqueue_output, args=(camoufox_proc.stderr, "stderr", camoufox_output_q, camoufox_proc.pid), daemon=True)
        camoufox_stdout_reader.start()
        camoufox_stderr_reader.start()

        ws_capture_start_time = time.time()
        camoufox_ended_streams_count = 0
        while time.time() - ws_capture_start_time < ENDPOINT_CAPTURE_TIMEOUT:
            if camoufox_proc.poll() is not None:
                logger.error(f"  Camoufox dahili süreci (PID: {camoufox_proc.pid}) WebSocket uç noktası beklenirken beklenmedik şekilde çıktı, çıkış kodu: {camoufox_proc.poll()}.")
                break
            try:
                stream_name, line_from_camoufox = camoufox_output_q.get(timeout=0.2)
                if line_from_camoufox is None:
                    camoufox_ended_streams_count += 1
                    logger.debug(f"  [InternalCamoufox-{stream_name}-PID:{camoufox_proc.pid}] çıktı akışı kapandı (EOF).")
                    if camoufox_ended_streams_count >= 2:
                        logger.info(f"  Camoufox dahili sürecinin (PID: {camoufox_proc.pid}) tüm çıktı akışları kapandı.")
                        break
                    continue

                log_line_content = f"[InternalCamoufox-{stream_name}-PID:{camoufox_proc.pid}]: {line_from_camoufox.rstrip()}"
                if stream_name == "stderr" or "ERROR" in line_from_camoufox.upper() or "❌" in line_from_camoufox:
                    logger.warning(log_line_content)
                else:
                    logger.info(log_line_content)

                ws_match = ws_regex.search(line_from_camoufox)
                if ws_match:
                    captured_ws_endpoint = ws_match.group(1)
                    logger.info(f"  ✅ Camoufox dahili sürecinden WebSocket uç noktası başarıyla alındı: {captured_ws_endpoint[:40]}...")
                    break
            except queue.Empty:
                continue

        if camoufox_stdout_reader.is_alive(): camoufox_stdout_reader.join(timeout=1.0)
        if camoufox_stderr_reader.is_alive(): camoufox_stderr_reader.join(timeout=1.0)

        if not captured_ws_endpoint and (camoufox_proc and camoufox_proc.poll() is None):
            logger.error(f" ❌ {ENDPOINT_CAPTURE_TIMEOUT} saniye içinde Camoufox dahili sürecinden (PID: {camoufox_proc.pid}) WebSocket uç noktası alınamadı.")
            logger.error(" Camoufox dahili süreci hâlâ çalışıyor, ancak beklenen WebSocket uç noktasını vermedi. Lütfen günlüklerini veya davranışını kontrol edin.")
            cleanup()
            sys.exit(1)
        elif not captured_ws_endpoint and (camoufox_proc and camoufox_proc.poll() is not None):
            logger.error(f"  ❌ Camoufox dahili süreci çıktı, ancak WebSocket uç noktası alınamadı.")
            sys.exit(1)
        elif not captured_ws_endpoint:
            logger.error(f" ❌ WebSocket uç noktası alınamadı.")
            sys.exit(1)

    except Exception as e_launch_camoufox_internal:
        logger.critical(f"  ❌ Camoufox'u dahili başlatırken veya WebSocket uç noktasını alırken kritik hata oluştu: {e_launch_camoufox_internal}", exc_info=True)
        cleanup()
        sys.exit(1)

    # --- Yardımcı mod mantığı (Yeni uygulama) ---
    if args.helper: # args.helper boş dize değilse (yani yardımcı işlevi varsayılan veya kullanıcı tarafından belirlenmiş şekilde etkinleştirildiyse)
        logger.info(f"  Yardımcı modu etkinleştirildi, uç nokta: {args.helper}")
        os.environ['HELPER_ENDPOINT'] = args.helper # Uç nokta ortam değişkenini ayarla

        if effective_active_auth_json_path:
            logger.info(f"    Kimlik doğrulama dosyasından '{os.path.basename(effective_active_auth_json_path)}' SAPISID alınıyor...")
            sapisid = ""
            try:
                with open(effective_active_auth_json_path, 'r', encoding='utf-8') as file:
                    auth_file_data = json.load(file)
                    if "cookies" in auth_file_data and isinstance(auth_file_data["cookies"], list):
                        for cookie in auth_file_data["cookies"]:
                            if isinstance(cookie, dict) and cookie.get("name") == "SAPISID" and cookie.get("domain") == ".google.com":
                                sapisid = cookie.get("value", "")
                                break
            except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"    ⚠️ Kimlik doğrulama dosyasından '{os.path.basename(effective_active_auth_json_path)}' SAPISID yüklenemedi veya çözümlenemedi: {e}")
            except Exception as e_sapisid_extraction:
                logger.warning(f"    ⚠️ SAPISID alınırken bilinmeyen hata oluştu: {e_sapisid_extraction}")

            if sapisid:
                logger.info(f"    ✅ SAPISID başarıyla yüklendi. HELPER_SAPISID ortam değişkeni ayarlanacak.")
                os.environ['HELPER_SAPISID'] = sapisid
            else:
                logger.warning(f"    ⚠️ Kimlik doğrulama dosyasında '{os.path.basename(effective_active_auth_json_path)}' geçerli SAPISID bulunamadı. HELPER_SAPISID ayarlanmayacak.")
                if 'HELPER_SAPISID' in os.environ: # Temizlik, önlem amaçlı
                    del os.environ['HELPER_SAPISID']
        else: # args.helper değerli (Yardımcı modu etkin), ancak kimlik doğrulama dosyası yok
            logger.warning(f"    ⚠️ Yardımcı modu etkinleştirildi, ancak SAPISID almak için geçerli kimlik doğrulama dosyası yok. HELPER_SAPISID ayarlanmayacak.")
            if 'HELPER_SAPISID' in os.environ: # Temizlik
                del os.environ['HELPER_SAPISID']
    else: # args.helper boş dize (kullanıcı --helper='' ile yardımcıyı devre dışı bıraktı)
        logger.info("  Yardımcı modu --helper='' ile devre dışı bırakıldı.")
        # İlgili ortam değişkenlerini temizle
        if 'HELPER_ENDPOINT' in os.environ:
            del os.environ['HELPER_ENDPOINT']
        if 'HELPER_SAPISID' in os.environ:
            del os.environ['HELPER_SAPISID']

    # --- Adım 4: Ortam değişkenlerini ayarla ve FastAPI/Uvicorn sunucusunu başlatmaya hazırla (dev'den) ---
    logger.info("--- Adım 4: Ortam değişkenlerini ayarla ve FastAPI/Uvicorn sunucusunu başlatmaya hazırla ---")

    if captured_ws_endpoint:
        os.environ['CAMOUFOX_WS_ENDPOINT'] = captured_ws_endpoint
    else:
        logger.error(" Kritik mantık hatası: WebSocket uç noktası alınmadı, ancak program devam ediyor.")
        sys.exit(1)

    os.environ['LAUNCH_MODE'] = final_launch_mode
    os.environ['SERVER_LOG_LEVEL'] = args.server_log_level.upper()
    os.environ['SERVER_REDIRECT_PRINT'] = str(args.server_redirect_print).lower()
    os.environ['DEBUG_LOGS_ENABLED'] = str(args.debug_logs).lower()
    os.environ['TRACE_LOGS_ENABLED'] = str(args.trace_logs).lower()
    if effective_active_auth_json_path:
        os.environ['ACTIVE_AUTH_JSON_PATH'] = effective_active_auth_json_path
    elif 'ACTIVE_AUTH_JSON_PATH' in os.environ:
        del os.environ['ACTIVE_AUTH_JSON_PATH']
    os.environ['AUTO_SAVE_AUTH'] = str(args.auto_save_auth).lower()
    if args.save_auth_as:
        os.environ['SAVE_AUTH_FILENAME'] = args.save_auth_as
    os.environ['AUTH_SAVE_TIMEOUT'] = str(args.auth_save_timeout)
    os.environ['SERVER_PORT_INFO'] = str(args.server_port)
    os.environ['STREAM_PORT'] = str(args.stream_port)

    # Birleşik proxy yapılandırması ortam değişkenini ayarla
    proxy_config = determine_proxy_configuration(args.internal_camoufox_proxy)
    if proxy_config['stream_proxy']:
        os.environ['UNIFIED_PROXY_CONFIG'] = proxy_config['stream_proxy']
        logger.info(f"  Birleşik proxy yapılandırması ayarlandı: {proxy_config['source']}")
    elif 'UNIFIED_PROXY_CONFIG' in os.environ:
        del os.environ['UNIFIED_PROXY_CONFIG']

    host_os_for_shortcut_env = None
    camoufox_os_param_lower = simulated_os_for_camoufox.lower()
    if camoufox_os_param_lower == "macos": host_os_for_shortcut_env = "Darwin"
    elif camoufox_os_param_lower == "windows": host_os_for_shortcut_env = "Windows"
    elif camoufox_os_param_lower == "linux": host_os_for_shortcut_env = "Linux"
    if host_os_for_shortcut_env:
        os.environ['HOST_OS_FOR_SHORTCUT'] = host_os_for_shortcut_env
    elif 'HOST_OS_FOR_SHORTCUT' in os.environ:
        del os.environ['HOST_OS_FOR_SHORTCUT']

    logger.info(f"  server.app için ortam değişkenleri:")
    env_keys_to_log = [
        'CAMOUFOX_WS_ENDPOINT', 'LAUNCH_MODE', 'SERVER_LOG_LEVEL',
        'SERVER_REDIRECT_PRINT', 'DEBUG_LOGS_ENABLED', 'TRACE_LOGS_ENABLED',
        'ACTIVE_AUTH_JSON_PATH', 'AUTO_SAVE_AUTH', 'SAVE_AUTH_FILENAME', 'AUTH_SAVE_TIMEOUT',
        'SERVER_PORT_INFO', 'HOST_OS_FOR_SHORTCUT',
        'HELPER_ENDPOINT', 'HELPER_SAPISID', 'STREAM_PORT',
        'UNIFIED_PROXY_CONFIG' # Yeni birleşik proxy yapılandırması eklendi
    ]
    for key in env_keys_to_log:
        if key in os.environ:
            val_to_log = os.environ[key]
            if key == 'CAMOUFOX_WS_ENDPOINT' and len(val_to_log) > 40: val_to_log = val_to_log[:40] + "..."
            if key == 'ACTIVE_AUTH_JSON_PATH': val_to_log = os.path.basename(val_to_log)
            logger.info(f"    {key}={val_to_log}")
        else:
            logger.info(f"    {key}= (ayarlanmadı)")


    # --- Adım 5: FastAPI/Uvicorn sunucusunu başlat (dev'den) ---
    logger.info(f"--- Adım 5: Entegre FastAPI sunucusunu başlat (dinleme portu: {args.server_port}) ---")

    if not args.exit_on_auth_save:
        try:
            uvicorn.run(
                app,
                host="0.0.0",
                port=args.server_port,
                log_config=None
            )
            logger.info("Uvicorn sunucusu durdu.")
        except SystemExit as e_sysexit:
            logger.info(f"Uvicorn veya alt sistemleri sys.exit({e_sysexit.code}) ile çıktı.")
        except Exception as e_uvicorn:
            logger.critical(f"❌ Uvicorn çalıştırılırken kritik hata oluştu: {e_uvicorn}", exc_info=True)
            sys.exit(1)
    else:
        logger.info("  --exit-on-auth-save etkin. Sunucu kimlik doğrulama kaydedildikten sonra otomatik olarak kapanacak.")

        server_config = uvicorn.Config(app, host="0.0.0.0", port=args.server_port, log_config=None)
        server = uvicorn.Server(server_config)

        stop_watcher = threading.Event()

        def watch_for_saved_auth_and_shutdown():
            os.makedirs(SAVED_AUTH_DIR, exist_ok=True)
            initial_files = set(os.listdir(SAVED_AUTH_DIR))
            logger.info(f"Kimlik doğrulama kaydetme dizini izlenmeye başlıyor: {SAVED_AUTH_DIR}")

            while not stop_watcher.is_set():
                try:
                    current_files = set(os.listdir(SAVED_AUTH_DIR))
                    new_files = current_files - initial_files
                    if new_files:
                        logger.info(f"Yeni kayıtlı kimlik doğrulama dosyaları tespit edildi: {', '.join(new_files)}. 3 saniye içinde kapatılacak...")
                        time.sleep(3)
                        server.should_exit = True
                        logger.info("Uvicorn sunucusuna kapatma sinyali gönderildi.")
                        break
                    initial_files = current_files
                except Exception as e:
                    logger.error(f"Kimlik doğrulama dizini izlenirken hata oluştu: {e}", exc_info=True)

                if stop_watcher.wait(1):
                    break
            logger.info("Kimlik doğrulama dosyası izleme iş parçacığı durdu.")

        watcher_thread = threading.Thread(target=watch_for_saved_auth_and_shutdown)

        try:
            watcher_thread.start()
            server.run()
            logger.info("Uvicorn sunucusu durdu.")
        except (KeyboardInterrupt, SystemExit) as e:
            event_name = "KeyboardInterrupt" if isinstance(e, KeyboardInterrupt) else f"SystemExit({getattr(e, 'code', '')})"
            logger.info(f"{event_name} alındı, kapatılıyor...")
        except Exception as e_uvicorn:
            logger.critical(f"❌ Uvicorn çalıştırılırken kritik hata oluştu: {e_uvicorn}", exc_info=True)
            sys.exit(1)
        finally:
            stop_watcher.set()
            if watcher_thread.is_alive():
                watcher_thread.join()

    logger.info("🚀 Camoufox başlatıcı ana mantığı tamamlandı 🚀")
