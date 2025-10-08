#!/usr/bin/env python3
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import subprocess
import os
import sys
import platform
import threading
import time
import socket
import signal
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import shlex
import logging
import json
import requests # Yeni eklenen içe aktarma
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

from config import ENABLE_QWEN_LOGIN_SUPPORT

# --- Configuration & Globals ---
PYTHON_EXECUTABLE = sys.executable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LAUNCH_CAMOUFOX_PY = os.path.join(SCRIPT_DIR, "launch_camoufox.py")
SERVER_PY_FILENAME = "server.py" # For context

AUTH_PROFILES_DIR = os.path.join(SCRIPT_DIR, "auth_profiles") # Bu dizinlerin varlığını sağla
ACTIVE_AUTH_DIR = os.path.join(AUTH_PROFILES_DIR, "active")
SAVED_AUTH_DIR = os.path.join(AUTH_PROFILES_DIR, "saved")

DEFAULT_FASTAPI_PORT = int(os.environ.get('DEFAULT_FASTAPI_PORT', '2048'))
DEFAULT_CAMOUFOX_PORT_GUI = int(os.environ.get('DEFAULT_CAMOUFOX_PORT', '9222'))  # launch_camoufox.py içindeki DEFAULT_CAMOUFOX_PORT ile uyumlu olmalı

managed_process_info: Dict[str, Any] = {
    "popen": None,
    "service_name_key": None,
    "monitor_thread": None,
    "stdout_thread": None,
    "stderr_thread": None,
    "output_area": None,
    "fully_detached": False # Yeni: sürecin tamamen bağımsız olup olmadığını işaretler
}

# Düğme debounce mekanizması ekle
button_debounce_info: Dict[str, float] = {}

def debounce_button(func_name: str, delay_seconds: float = 2.0):
    """
    Düğme debounce dekoratörü, belirtilen süre içinde aynı işlevin tekrar tekrar yürütülmesini önler
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            current_time = time.time()
            last_call_time = button_debounce_info.get(func_name, 0)

            if current_time - last_call_time < delay_seconds:
                logger.info(f"Düğme debounce: {func_name} tekrar çağrısı yoksayılıyor")
                return

            button_debounce_info[func_name] = current_time
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Global logger tanımı ekle
logger = logging.getLogger("GUILauncher")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)
os.makedirs(os.path.join(SCRIPT_DIR, "logs"), exist_ok=True)
file_handler = logging.FileHandler(os.path.join(SCRIPT_DIR, "logs", "gui_launcher.log"), encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# LANG_TEXTS bildirimi öncesi uzun metinleri tanımlayın
service_closing_guide_message_zh = """Hizmet bağımsız bir terminalde çalıştığı için, hizmeti aşağıdaki yollarla kapatabilirsiniz:

1. Port yönetimi işlevini kullanma:
   - "Port işlemlerini sorgula" düğmesine tıklayın
   - İlgili Python işlemini seçin
   - "Seçilen işlemi durdur" seçeneğine tıklayın

2. İşlemi manuel olarak sonlandırma:
   - Windows: Görev Yöneticisini kullan
   - macOS: Activity Monitor veya terminal kullan
   - Linux: kill komutunu kullan

3. Hizmetin çalıştığı terminal penceresini doğrudan kapat"""

service_closing_guide_message_en = """Since the service runs in an independent terminal, you can close it using these methods:

1. Using port management in GUI:
   - Click "Query Port Processes" button
   - Select the relevant Python process
   - Click "Stop Selected Process"

2. Manually terminate process:
   - Windows: Use Task Manager
   - macOS: Use Activity Monitor or terminal
   - Linux: Use kill command

3. Directly close the terminal window running the service"""

# --- Uluslararasılaştırma (i18n) ---
LANG_TEXTS = {
    "title": {"zh": "AI Studio Proxy API Başlatıcı Arayüzü", "en": "AI Studio Proxy API Launcher GUI"},
    "status_idle": {"zh": "Boşta, bir işlem seçin.", "en": "Idle. Select an action."},
    "port_section_label": {"zh": "Servis Port Yapılandırması", "en": "Service Port Configuration"},
    "port_input_description_lbl": {"zh": "Not: Aşağıda belirtilen FastAPI servis portu ve Camoufox hata ayıklama portu başlatma için kullanılacaktır.", "en": "Note: The FastAPI service port and Camoufox debug port specified below will be used for launch."},
    "fastapi_port_label": {"zh": "FastAPI Servis Portu:", "en": "FastAPI Port:"},
    "camoufox_debug_port_label": {"zh": "Camoufox Hata Ayıklama Portu:", "en": "Camoufox Debug Port:"},
    "query_pids_btn": {"zh": "Port İşlemlerini Sorgula", "en": "Query Port Processes"},
    "stop_selected_pid_btn": {"zh": "Seçilen İşlemi Durdur", "en": "Stop Selected Process"},
    "pids_on_port_label": {"zh": "Port Kullanım Durumu (PID - Ad):", "en": "Processes on Port (PID - Name):"}, # Static version for initialization
    "pids_on_port_label_dynamic": {"zh": "Port {port} Kullanım Durumu (PID - Ad):", "en": "Processes on Port {port} (PID - Name):"}, # Dynamic version
    "no_pids_found": {"zh": "Bu portta işlem bulunamadı.", "en": "No processes found on this port."},
    "static_pid_list_title": {"zh": "Başlatma İçin Gerekli Port Kullanımı (PID - Ad)", "en": "Required Ports Usage (PID - Name)"}, # Yeni başlık
    "launch_options_label": {"zh": "Başlatma Seçenekleri", "en": "Launch Options"},
    "launch_options_note_revised": {"zh": "İpucu: Başlıklı/Başlıksız modlar hizmeti yeni bağımsız bir terminal penceresinde başlatır.\nBaşlıklı mod hata ayıklama ve kimlik doğrulama içindir. Başlıksız mod önceden kimlik doğrulaması gerektirir.\nBu arayüzü kapatmak bağımsız olarak başlatılan hizmetleri durdurmaz.",
                                    "en": "Tip: Headed/Headless modes will launch the service in a new independent terminal window.\nHeaded mode is for debug and auth. Headless mode requires pre-auth.\nClosing this GUI will NOT stop independently launched services."},
    "launch_headed_interactive_btn": {"zh": "Başlıklı Modu Başlat (Yeni Terminal)", "en": "Launch Headed Mode (New Terminal)"},
    "launch_headless_btn": {"zh": "Başlıksız Modu Başlat (Yeni Terminal)", "en": "Launch Headless Mode (New Terminal)"},
    "launch_virtual_display_btn": {"zh": "Sanal Ekran Modunu Başlat (Linux)", "en": "Launch Virtual Display (Linux)"},
    "stop_gui_service_btn": {"zh": "Mevcut Arayüzle Yönetilen Hizmeti Durdur", "en": "Stop Current GUI-Managed Service"},
    "status_label": {"zh": "Durum", "en": "Status"},
    "output_label": {"zh": "Çıktı Günlüğü", "en": "Output Log"},
    "menu_language_fixed": {"zh": "Language", "en": "Language"},
    "menu_lang_zh_option": {"zh": "Çince (Chinese)", "en": "Çince (Chinese)"},
    "menu_lang_en_option": {"zh": "İngilizce (English)", "en": "İngilizce (English)"},
    "confirm_quit_title": {"zh": "Çıkışı Onayla", "en": "Confirm Quit"},
    "confirm_quit_message": {"zh": "Hizmetler hala bağımsız terminallerde çalışabilir. Arayüzden çıkmayı onaylıyor musunuz?", "en": "Services may still be running in independent terminals. Confirm quit GUI?"},
    "confirm_quit_message_independent": {"zh": "Bağımsız arka plan hizmeti '{service_name}' hala çalışıyor olabilir. Arayüzden çıkılsın mı (hizmet çalışmaya devam edecek)?", "en": "Independent background service '{service_name}' may still be running. Quit GUI (service will continue to run)?"},
    "error_title": {"zh": "Hata", "en": "Error"},
    "info_title": {"zh": "Bilgi", "en": "Info"},
    "warning_title": {"zh": "Uyarı", "en": "Warning"},
    "service_already_running": {"zh": "Hizmet ({service_name}) zaten çalışıyor.", "en": "A service ({service_name}) is already running."},
    "proxy_config_title": {"zh": "Proxy Yapılandırması", "en": "Proxy Configuration"},
    "proxy_config_message_generic": {"zh": "Bu başlatma için HTTP/HTTPS proxy etkinleştirilsin mi?", "en": "Enable HTTP/HTTPS proxy for this launch?"},
    "proxy_address_title": {"zh": "Proxy Adresi", "en": "Proxy Address"},
    "proxy_address_prompt": {"zh": "Proxy adresini girin (örneğin http://host:port)\nVarsayılan: {default_proxy}", "en": "Enter proxy address (e.g., http://host:port)\nDefault: {default_proxy}"},
    "proxy_configured_status": {"zh": "Proxy yapılandırıldı: {proxy_addr}", "en": "Proxy configured: {proxy_addr}"},
    "proxy_skip_status": {"zh": "Kullanıcı proxy kurulumunu atladı.", "en": "Proxy setup skipped by user."},
    "script_not_found_error_msgbox": {"zh": "Başlatma başarısız oldu: Python yürütülebilir dosyası veya komut dosyası bulunamadı.\nKomut: {cmd}", "en": "Failed to start: Python executable or script not found.\nCommand: {cmd}"},
    "startup_error_title": {"zh": "Başlatma Hatası", "en": "Startup Error"},
    "startup_script_not_found_msgbox": {"zh": "Gerekli komut dosyası '{script}' mevcut dizinde bulunamadı.\nBu GUI başlatıcısını launch_camoufox.py ve server.py ile aynı dizine yerleştirin.", "en": "Required script '{script}' not found in the current directory.\nPlace this GUI launcher in the same directory as launch_camoufox.py and server.py."},
    "service_starting_status": {"zh": "{service_name} başlatılıyor... PID: {pid}", "en": "{service_name} starting... PID: {pid}"},
    "service_stopped_gracefully_status": {"zh": "{service_name} düzgün şekilde durduruldu.", "en": "{service_name} stopped gracefully."},
    "service_stopped_exit_code_status": {"zh": "{service_name} durduruldu. Çıkış kodu: {code}", "en": "{service_name} stopped. Exit code: {code}"},
    "service_stop_fail_status": {"zh": "{service_name} (PID: {pid}) düzgün şekilde sonlandırılamadı. Zorla durduruluyor...", "en": "{service_name} (PID: {pid}) did not terminate gracefully. Forcing kill..."},
    "service_killed_status": {"zh": "{service_name} (PID: {pid}) zorla durduruldu.", "en": "{service_name} (PID: {pid}) killed."},
    "error_stopping_service_msgbox": {"zh": "{service_name} (PID: {pid}) durdurulurken hata oluştu: {e}", "en": "Error stopping {service_name} (PID: {pid}): {e}"},
    "no_service_running_status": {"zh": "Şu anda arayüzle yönetilen hizmet yok.", "en": "No GUI-managed service is currently running."},
    "stopping_initiated_status": {"zh": "{service_name} (PID: {pid}) durdurma başlatıldı. Nihai durum bekleniyor.", "en": "{service_name} (PID: {pid}) stopping initiated. Final status pending."},
    "service_name_headed_interactive": {"zh": "Başlıklı Etkileşimli Hizmet", "en": "Headed Interactive Service"},
    "service_name_headless": {"zh": "Başlıksız Hizmet", "en": "Headless Service"}, # Anahtar değiştirildi
    "service_name_virtual_display": {"zh": "Sanal Ekran Başlıksız Hizmet", "en": "Virtual Display Headless Service"},
    "status_headed_launch": {"zh": "Başlıklı Mod: Başlatılıyor, yeni konsoldaki istemleri kontrol edin...", "en": "Headed Mode: Launching, check new console for prompts..."},
    "status_headless_launch": {"zh": "Başlıksız Hizmet: Başlatılıyor... Yeni bağımsız terminal açılacak.", "en": "Headless Service: Launching... A new independent terminal will open."},
    "status_virtual_display_launch": {"zh": "Sanal Ekran Modu başlatılıyor...", "en": "Virtual Display Mode launching..."},
    "info_service_is_independent": {"zh": "Mevcut hizmet bağımsız bir arka plan işlemidir, arayüzü kapatmak onu durdurmaz. Lütfen bu hizmeti sistem araçlarını veya port yönetimini kullanarak manuel olarak yönetin.", "en": "The current service is an independent background process. Closing the GUI will not stop it. Please manage this service manually using system tools or port management."},
    "info_service_new_terminal": {"zh": "Hizmet yeni bağımsız bir terminalde başlatıldı. Bu arayüzü kapatmak hizmeti etkilemez.", "en": "Service has been launched in a new independent terminal. Closing this GUI will not affect the service."},
    "warn_cannot_stop_independent_service": {"zh": "Bu arayüzle başlatılan hizmetler bağımsız terminallerde çalışır ve bu düğmeyle durdurulamaz. Lütfen doğrudan terminallerini yönetin veya sistem araçlarını kullanın.", "en": "Services launched via this GUI run in independent terminals and cannot be stopped by this button. Please manage their terminals directly or use system tools."},
    "enter_valid_port_warn": {"zh": "Lütfen geçerli bir port numarası girin (1024-65535).", "en": "Please enter a valid port number (1024-65535)."},
    "pid_list_empty_for_stop_warn": {"zh": "PID listesi boş veya işlem seçilmedi.", "en": "PID list is empty or no process selected."},
    "confirm_stop_pid_title": {"zh": "İşlem Durdurmayı Onayla", "en": "Confirm Stop Process"},
    "confirm_stop_pid_message": {"zh": "PID {pid} ({name}) durdurma girişiminde emin misiniz?", "en": "Are you sure you want to attempt to stop PID {pid} ({name})?"},
    "confirm_stop_pid_admin_title": {"zh": "Yönetici Ayrıcalıklarıyla İşlemi Durdur", "en": "Stop Process with Admin Privileges"},
    "confirm_stop_pid_admin_message": {"zh": "PID {pid} ({name}) normal ayrıcalıklarla durdurulması başarısız olabilir. Yönetici ayrıcalıklarıyla denensin mi?", "en": "Stopping PID {pid} ({name}) with normal privileges may fail. Try with admin privileges?"},
    "admin_stop_success": {"zh": "PID {pid} yönetici ayrıcalıklarıyla başarıyla durduruldu", "en": "Successfully stopped PID {pid} with admin privileges"},
    "admin_stop_failure": {"zh": "PID {pid} yönetici ayrıcalıklarıyla durdurulamadı: {error}", "en": "Failed to stop PID {pid} with admin privileges: {error}"},
    "status_error_starting": {"zh": "{service_name} başlatma başarısız oldu.", "en": "Error starting {service_name}"},
    "status_script_not_found": {"zh": "Hata: {service_name} için yürütülebilir/dosya bulunamadı.", "en": "Error: Executable/script not found for {service_name}."},
    "error_getting_process_name": {"zh": "PID {pid} için işlem adı alınamadı.", "en": "Failed to get process name for PID {pid}."},
    "pid_info_format": {"zh": "PID: {pid} (Port: {port}) - Ad: {name}", "en": "PID: {pid} (Port: {port}) - Name: {name}"},
    "status_stopping_service": {"zh": "{service_name} (PID: {pid}) durduruluyor...", "en": "Stopping {service_name} (PID: {pid})..."},
    "error_title_invalid_selection": {"zh": "Geçersiz seçim formatı: {selection}", "en": "Invalid selection format: {selection}"},
    "error_parsing_pid": {"zh": "'{selection}' içinden PID ayrıştırılamadı.", "en": "Could not parse PID from '{selection}'."},
    "terminate_request_sent": {"zh": "Sonlandırma isteği gönderildi.", "en": "Termination request sent."},
    "terminate_attempt_failed": {"zh": "PID {pid} ({name}) sonlandırma girişimi başarısız olabilir.", "en": "Attempt to terminate PID {pid} ({name}) may have failed."},
    "unknown_process_name_placeholder": {"zh": "Bilinmeyen İşlem Adı", "en": "Unknown Process Name"},
    "kill_custom_pid_label": {"zh": "Veya Sonlandırmak İçin PID Girin:", "en": "Or Enter PID to Kill:"},
    "kill_custom_pid_btn": {"zh": "Belirtilen PID'yi Sonlandır", "en": "Kill Specified PID"},
    "pid_input_empty_warn": {"zh": "Lütfen sonlandırmak için bir PID girin.", "en": "Please enter a PID to kill."},
    "pid_input_invalid_warn": {"zh": "Geçersiz PID girildi, lütfen sadece sayı girin.", "en": "Invalid PID entered. Please enter numbers only."},
    "confirm_kill_custom_pid_title": {"zh": "PID Sonlandırmayı Onayla", "en": "Confirm Kill PID"},
    "status_sending_sigint": {"zh": "{service_name} (PID: {pid}) SIGINT gönderiliyor...", "en": "Sending SIGINT to {service_name} (PID: {pid})..."},
    "status_waiting_after_sigint": {"zh": "{service_name} (PID: {pid}): SIGINT gönderildi, {timeout} saniye düzgün çıkış için bekleniyor...", "en": "{service_name} (PID: {pid}): SIGINT sent, waiting {timeout}s for graceful exit..."},
    "status_sigint_effective": {"zh": "{service_name} (PID: {pid}) SIGINT'e yanıt verdi ve durdu.", "en": "{service_name} (PID: {pid}) responded to SIGINT and stopped."},
    "status_sending_sigterm": {"zh": "{service_name} (PID: {pid}): Zamanında SIGINT'e yanıt vermedi, SIGTERM gönderiliyor...", "en": "{service_name} (PID: {pid}): Did not respond to SIGINT in time, sending SIGTERM..."},
    "status_waiting_after_sigterm": {"zh": "{service_name} (PID: {pid}): SIGTERM gönderildi, {timeout} saniye düzgün çıkış için bekleniyor...", "en": "{service_name} (PID: {pid}): SIGTERM sent, waiting {timeout}s for graceful exit..."},
    "status_sigterm_effective": {"zh": "{service_name} (PID: {pid}) SIGTERM'e yanıt verdi ve durdu.", "en": "{service_name} (PID: {pid}) responded to SIGTERM and stopped."},
    "status_forcing_kill": {"zh": "{service_name} (PID: {pid}): Zamanında SIGTERM'e yanıt vermedi, zorla sonlandırılıyor (SIGKILL)...", "en": "{service_name} (PID: {pid}): Did not respond to SIGTERM in time, forcing kill (SIGKILL)..."},
    "enable_stream_proxy_label": {"zh": "Akış Proxy Hizmetini Etkinleştir", "en": "Enable Stream Proxy Service"},
    "stream_proxy_port_label": {"zh": "Akış Proxy Portu:", "en": "Stream Proxy Port:"},
    "enable_helper_label": {"zh": "Harici Yardımcı Hizmeti Etkinleştir", "en": "Enable External Helper Service"},
    "helper_endpoint_label": {"zh": "Yardımcı Uç Nokta URL'si:", "en": "Helper Endpoint URL:"},
    "auth_manager_title": {"zh": "Kimlik Doğrulama Dosyası Yöneticisi", "en": "Authentication File Manager"},
    "saved_auth_files_label": {"zh": "Kayıtlı Kimlik Doğrulama Dosyaları:", "en": "Saved Authentication Files:"},
    "no_file_selected": {"zh": "Lütfen bir kimlik doğrulama dosyası seçin", "en": "Please select an authentication file"},
    "auth_file_activated": {"zh": "Kimlik doğrulama dosyası '{file}' başarıyla etkinleştirildi", "en": "Authentication file '{file}' has been activated successfully"},
    "error_activating_file": {"zh": "Dosya '{file}' etkinleştirilirken hata oluştu: {error}", "en": "Error activating file '{file}': {error}"},
    "activate_selected_btn": {"zh": "Seçilen Dosyayı Etkinleştir", "en": "Activate Selected File"},
    "deactivate_btn": {"zh": "Mevcut Kimlik Doğrulamayı Kaldır", "en": "Remove Current Auth"},
    "confirm_deactivate_title": {"zh": "Kimlik Doğrulama Kaldırmayı Onayla", "en": "Confirm Auth Removal"},
    "confirm_deactivate_message": {"zh": "Mevcut etkin kimlik doğrulamayı kaldırmak istediğinizden emin misiniz? Bu, sonraki başlatmaların kimlik doğrulama dosyası kullanmamasına neden olur.", "en": "Are you sure you want to remove the currently active authentication? This will cause subsequent launches to use no authentication file."},
    "auth_deactivated_success": {"zh": "Mevcut kimlik doğrulama başarıyla kaldırıldı.", "en": "Successfully removed current authentication."},
    "error_deactivating_auth": {"zh": "Kimlik doğrulama kaldırılırken hata oluştu: {error}", "en": "Error removing authentication: {error}"},
    "create_new_auth_btn": {"zh": "Yeni Kimlik Doğrulama Dosyası Oluştur", "en": "Create New Auth File"},
    "create_new_auth_instructions_title": {"zh": "Yeni Kimlik Doğrulama Dosyası Oluşturma Talimatları", "en": "Create New Auth File Instructions"},
    "create_new_auth_instructions_message": {"zh": "Giriş yapmanız için yeni bir tarayıcı penceresi açılacak.\n\nBaşarılı girişten sonra, bu programı çalıştıran terminale dönün ve kimlik doğrulama bilgilerinizi kaydetmek için istemde bulunun.\n\nDevam etmek için Tamam'a tıklayın.", "en": "A new browser window will open for you to log in.\n\nAfter successful login, please return to the terminal running this program and enter a filename to save your authentication credentials when prompted.\n\nClick OK when you are ready to proceed."},
    "create_new_auth_instructions_message_revised": {"zh": "Giriş yapmanız için yeni bir tarayıcı penceresi açılacak.\n\nBaşarılı girişten sonra, kimlik doğrulama dosyası '{filename}.json' olarak otomatik olarak kaydedilecek.\n\nDevam etmek için Tamam'a tıklayın.", "en": "A new browser window will open for you to log in.\n\nAfter successful login, the authentication file will be automatically saved as '{filename}.json'.\n\nClick OK when you are ready to proceed."},
    "create_new_auth_filename_prompt_title": {"zh": "Kimlik Doğrulama Dosyası Adını Girin", "en": "Enter Auth Filename"},
    "service_name_auth_creation": {"zh": "Kimlik Doğrulama Dosyası Oluşturma Hizmeti", "en": "Auth File Creation Service"},
    "cancel_btn": {"zh": "İptal", "en": "Cancel"},
    "auth_files_management": {"zh": "Kimlik Doğrulama Dosyaları Yönetimi", "en": "Auth Files Management"},
    "manage_auth_files_btn": {"zh": "Kimlik Doğrulama Dosyalarını Yönet", "en": "Manage Auth Files"},
    "no_saved_auth_files": {"zh": "Kayıtlı dizinde kimlik doğrulama dosyası yok", "en": "No authentication files in saved directory"},
    "auth_dirs_missing": {"zh": "Kimlik doğrulama dizinleri eksik, lütfen doğru dizin yapısını sağlayın", "en": "Authentication directories missing, please ensure correct directory structure"},
    "auth_disabled_title": {"zh": "Oturum Açma Devre Dışı", "en": "Login Disabled"},
    "auth_disabled_message": {"zh": "Qwen modunda oturum açma desteği devre dışı; kimlik doğrulama dosyaları kullanılmaz.", "en": "Qwen login support is disabled; authentication files are not used."},
    "confirm_kill_port_title": {"zh": "Port Temizliğini Onayla", "en": "Confirm Port Cleanup"},
    "confirm_kill_port_message": {"zh": "Port {port} şu PID(ler) tarafından kullanılıyor: {pids}. Bu işlemleri sonlandırmayı denesin mi?", "en": "Port {port} is in use by PID(s): {pids}. Try to terminate them?"},
    "port_cleared_success": {"zh": "Port {port} başarıyla temizlendi", "en": "Port {port} has been cleared successfully"},
    "port_still_in_use": {"zh": "Port {port} hala kullanımda, lütfen manuel olarak işlem yapın", "en": "Port {port} is still in use, please handle manually"},
    "port_in_use_no_pids": {"zh": "Port {port} kullanımda, ancak işlemler tanımlanamıyor", "en": "Port {port} is in use, but processes cannot be identified"},
    "error_removing_file": {"zh": "Dosya '{file}' kaldırılırken hata oluştu: {error}", "en": "Error removing file '{file}': {error}"},
    "stream_port_out_of_range": {"zh": "Akış proxy portu 0 (devre dışı) veya 1024-65535 arası bir değer olmalıdır", "en": "Stream proxy port must be 0 (disabled) or a value between 1024-65535"},
    "port_auto_check": {"zh": "Başlamadan önce otomatik port kontrolü", "en": "Auto-check port before launch"},
    "auto_port_check_enabled": {"zh": "Port otomatik kontrolü etkinleştirildi", "en": "Port auto-check enabled"},
    "port_check_running": {"zh": "Port {port} kontrol ediliyor...", "en": "Checking port {port}..."},
    "port_name_fastapi": {"zh": "FastAPI Hizmeti", "en": "FastAPI Service"},
    "port_name_camoufox_debug": {"zh": "Camoufox Hata Ayıklama", "en": "Camoufox Debug"},
    "port_name_stream_proxy": {"zh": "Akış Proxy", "en": "Stream Proxy"},
    "checking_port_with_name": {"zh": "{port_name} port {port} kontrol ediliyor...", "en": "Checking {port_name} port {port}..."},
    "port_check_all_completed": {"zh": "Tüm port kontrolleri tamamlandı", "en": "All port checks completed"},
    "port_check_failed": {"zh": "{port_name} port {port} kontrolü başarısız oldu, başlatma iptal edildi", "en": "{port_name} port {port} check failed, launch aborted"},
    "port_name_helper_service": {"zh": "Yardımcı Hizmet", "en": "Helper Service"},
    "confirm_kill_multiple_ports_title": {"zh": "Çoklu Port Temizliğini Onayla", "en": "Confirm Multiple Ports Cleanup"},
    "confirm_kill_multiple_ports_message": {"zh": "Aşağıdaki portlar kullanımda:\n{occupied_ports_details}\nBu işlemleri sonlandırmayı denensin mi?", "en": "The following ports are in use:\n{occupied_ports_details}\nAttempt to terminate these processes?"},
    "all_ports_cleared_success": {"zh": "Tüm seçilen portlar başarıyla temizlendi.", "en": "All selected ports have been cleared successfully."},
    "some_ports_still_in_use": {"zh": "Temizleme girişiminden sonra bazı portlar hala kullanımda, lütfen manuel olarak işlem yapın. Başlatma iptal edildi.", "en": "Some ports are still in use after cleanup attempt. Please handle manually. Launch aborted."},
    "port_check_user_declined_cleanup": {"zh": "Kullanıcı meşgul portları temizlemeyi seçmedi. Başlatma iptal edildi.", "en": "User chose not to clean up occupied ports. Launch aborted."},
    "reset_button": {"zh": "Varsayılanlara Sıfırla", "en": "Reset to Defaults"},
    "confirm_reset_title": {"zh": "Sıfırlamayı Onayla", "en": "Confirm Reset"},
    "confirm_reset_message": {"zh": "Tüm ayarları varsayılan değerlere sıfırlamak istediğinizden emin misiniz?", "en": "Are you sure you want to reset all settings to default values?"},
    "reset_success": {"zh": "Varsayılan ayarlara başarıyla sıfırlandı", "en": "Reset to default settings successfully"},
    "proxy_config_last_used": {"zh": "Son proxy kullanılıyor: {proxy}", "en": "Using last proxy: {proxy}"},
    "proxy_config_other": {"zh": "Farklı bir proxy adresi kullan", "en": "Use a different proxy address"},
    "service_closing_guide": {"zh": "Hizmeti Kapatma Rehberi", "en": "Service Closing Guide"},
    "service_closing_guide_btn": {"zh": "Hizmeti Nasıl Kapatırım?", "en": "How to Close Service?"},
    "service_closing_guide_message": {"zh": service_closing_guide_message_zh, "en": service_closing_guide_message_en},
    "enable_proxy_label": {"zh": "Tarayıcı Proxy'sini Etkinleştir", "en": "Enable Browser Proxy"},
    "proxy_address_label": {"zh": "Proxy Adresi:", "en": "Proxy Address:"},
    "current_auth_file_display_label": {"zh": "Mevcut Kimlik Doğrulama: ", "en": "Current Auth: "},
    "current_auth_file_none": {"zh": "Yok", "en": "None"},
    "current_auth_file_selected_format": {"zh": "{file}", "en": "{file}"},
    "test_proxy_btn": {"zh": "Test", "en": "Test"},
    "proxy_section_label": {"zh": "Proxy Yapılandırması", "en": "Proxy Configuration"},
    "proxy_test_url_default": "http://httpbin.org/get", # Varsayılan test URL'si
    "proxy_test_url_backup": "http://www.google.com", # Yedek test URL'si
    "proxy_not_enabled_warn": {"zh": "Proxy etkin değil veya adres boş, lütfen önce yapılandırın.", "en": "Proxy not enabled or address is empty. Please configure first."},
    "proxy_test_success": {"zh": "Proxy bağlantısı başarılı ({url})", "en": "Proxy connection successful ({url})"},
    "proxy_test_failure": {"zh": "Proxy bağlantısı başarısız ({url}):\n{error}", "en": "Proxy connection failed ({url}):\n{error}"},
    "proxy_testing_status": {"zh": "Proxy {proxy_addr} test ediliyor...", "en": "Testing proxy {proxy_addr}..."},
    "proxy_test_success_status": {"zh": "Proxy testi başarılı ({url})", "en": "Proxy test successful ({url})"},
    "proxy_test_failure_status": {"zh": "Proxy testi başarısız: {error}", "en": "Proxy test failed: {error}"},
    "proxy_test_retrying": {"zh": "Proxy testi başarısız, yeniden deneniyor ({attempt}/{max_attempts})...", "en": "Proxy test failed, retrying ({attempt}/{max_attempts})..."},
    "proxy_test_backup_url": {"zh": "Birincil test URL'si başarısız oldu, yedek URL deneniyor...", "en": "Primary test URL failed, trying backup URL..."},
    "proxy_test_all_failed": {"zh": "Tüm proxy testi denemeleri başarısız oldu", "en": "All proxy test attempts failed"},
    "querying_ports_status": {"zh": "Port sorgulanıyor: {ports_desc}...", "en": "Querying ports: {ports_desc}..."},
    "port_query_result_format": {"zh": "[{port_type} - {port_num}] {pid_info}", "en": "[{port_type} - {port_num}] {pid_info}"},
    "port_not_in_use_format": {"zh": "[{port_type} - {port_num}] Kullanımda değil", "en": "[{port_type} - {port_num}] Not in use"},
    "pids_on_multiple_ports_label": {"zh": "Çoklu Port Kullanımı:", "en": "Multi-Port Usage:"},
    "launch_llm_service_btn": {"zh": "Yerel LLM Sahte Hizmetini Başlat", "en": "Launch Local LLM Mock Service"},
    "stop_llm_service_btn": {"zh": "Yerel LLM Sahte Hizmetini Durdur", "en": "Stop Local LLM Mock Service"},
    "llm_service_name_key": {"zh": "Yerel LLM Sahte Hizmeti", "en": "Local LLM Mock Service"},
    "status_llm_starting": {"zh": "Yerel LLM Sahte Hizmeti başlatılıyor (PID: {pid})...", "en": "Local LLM Mock Service starting (PID: {pid})..."},
    "status_llm_stopped": {"zh": "Yerel LLM Sahte Hizmeti durduruldu.", "en": "Local LLM Mock Service stopped."},
    "status_llm_stop_error": {"zh": "Yerel LLM Sahte Hizmeti durdurulurken hata oluştu.", "en": "Error stopping Local LLM Mock Service."},
    "status_llm_already_running": {"zh": "Yerel LLM Sahte Hizmeti zaten çalışıyor (PID: {pid}).", "en": "Local LLM Mock Service is already running (PID: {pid})."},
    "status_llm_not_running": {"zh": "Yerel LLM Sahte Hizmeti çalışmıyor.", "en": "Local LLM Mock Service is not running."},
    "status_llm_backend_check": {"zh": "LLM arka uç hizmeti kontrol ediliyor ...", "en": "Checking LLM backend service ..."},
    "status_llm_backend_ok_starting": {"zh": "LLM arka uç hizmeti (localhost:{port}) tamam, sahte hizmet başlatılıyor...", "en": "LLM backend service (localhost:{port}) OK, starting mock service..."},
    "status_llm_backend_fail": {"zh": "LLM arka uç hizmeti (localhost:{port}) yanıt vermiyor, sahte hizmet başlatılamıyor.", "en": "LLM backend service (localhost:{port}) not responding, cannot start mock service."},
    "confirm_stop_llm_title": {"zh": "LLM Hizmetini Durdurmayı Onayla", "en": "Confirm Stop LLM Service"},
    "confirm_stop_llm_message": {"zh": "Yerel LLM Sahte Hizmetini durdurmak istediğinizden emin misiniz?", "en": "Are you sure you want to stop the Local LLM Mock Service?"},
    "create_new_auth_filename_prompt": {"zh": "Kimlik doğrulama bilgilerini kaydetmek için dosya adı girin:", "en": "Please enter the filename to save authentication credentials:"},
    "invalid_auth_filename_warn": {"zh": "Geçersiz dosya adı. Lütfen sadece harf, rakam, - ve _ kullanın.", "en": "Invalid filename. Please use only letters, numbers, -, and _."},
    "confirm_save_settings_title": {"zh": "Ayarları Kaydet", "en": "Save Settings"},
    "confirm_save_settings_message": {"zh": "Mevcut ayarları kaydetmek istiyor musunuz?", "en": "Do you want to save the current settings?"},
    "settings_saved_success": {"zh": "Ayarlar başarıyla kaydedildi.", "en": "Settings saved successfully."},
    "save_now_btn": {"zh": "Şimdi Kaydet", "en": "Save Now"}
}

# Yinelenen tanımları kaldır
current_language = 'zh'
root_widget: Optional[tk.Tk] = None
process_status_text_var: Optional[tk.StringVar] = None
port_entry_var: Optional[tk.StringVar] = None # FastAPI portu için kullanılacak
camoufox_debug_port_var: Optional[tk.StringVar] = None
pid_listbox_widget: Optional[tk.Listbox] = None
custom_pid_entry_var: Optional[tk.StringVar] = None
widgets_to_translate: List[Dict[str, Any]] = []
proxy_address_var: Optional[tk.StringVar] = None  # Proxy adresini saklamak için değişken ekle
proxy_enabled_var: Optional[tk.BooleanVar] = None  # Proxy'nin etkin olup olmadığını takip etmek için değişken
active_auth_file_display_var: Optional[tk.StringVar] = None # Aktif kimlik doğrulama dosyasını göstermek için kullanılır
g_config: Dict[str, Any] = {} # Yüklenen yapılandırmayı saklamak için global depolama

LLM_PY_FILENAME = "llm.py"
llm_service_process_info: Dict[str, Any] = {
    "popen": None,
    "monitor_thread": None,
    "stdout_thread": None,
    "stderr_thread": None,
    "service_name_key": "llm_service_name_key" # LANG_TEXTS anahtarına karşılık gelir
}

# Tüm yardımcı fonksiyon tanımlarını build_gui'den önce taşıyın

def get_text(key: str, **kwargs) -> str:
    try:
        text_template = LANG_TEXTS[key][current_language]
    except KeyError:
        text_template = LANG_TEXTS[key].get('en', f"<{key}_MISSING_{current_language}>")
    return text_template.format(**kwargs) if kwargs else text_template

def update_status_bar(message_key: str, **kwargs):
    message = get_text(message_key, **kwargs)

    def _perform_gui_updates():
        # Update the status bar label's text variable
        if process_status_text_var:
            process_status_text_var.set(message)

        # Update the main log text area (if it exists)
        if managed_process_info.get("output_area"):
            # The 'message' variable is captured from the outer scope (closure)
            if root_widget: # Ensure root_widget is still valid
                output_area_widget = managed_process_info["output_area"]
                output_area_widget.config(state=tk.NORMAL)
                output_area_widget.insert(tk.END, f"[STATUS] {message}\n")
                output_area_widget.see(tk.END)
                output_area_widget.config(state=tk.DISABLED)

    if root_widget:
        root_widget.after_idle(_perform_gui_updates)

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", port))
            return False
        except OSError: return True
        except Exception: return True

def get_process_name_by_pid(pid: int) -> str:
    system = platform.system()
    name = get_text("unknown_process_name_placeholder")
    cmd_args = []
    try:
        if system == "Windows":
            cmd_args = ["tasklist", "/NH", "/FO", "CSV", "/FI", f"PID eq {pid}"]
            process = subprocess.run(cmd_args, capture_output=True, text=True, check=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if process.stdout.strip():
                parts = process.stdout.strip().split('","')
                if len(parts) > 0: name = parts[0].strip('"')
        elif system == "Linux":
            cmd_args = ["ps", "-p", str(pid), "-o", "comm="]
            process = subprocess.run(cmd_args, capture_output=True, text=True, check=True, timeout=3)
            if process.stdout.strip(): name = process.stdout.strip()
        elif system == "Darwin":
            cmd_args = ["ps", "-p", str(pid), "-o", "comm="]
            process = subprocess.run(cmd_args, capture_output=True, text=True, check=True, timeout=3)
            raw_path = process.stdout.strip() if process.stdout.strip() else ""
            cmd_args = ["ps", "-p", str(pid), "-o", "command="]
            process = subprocess.run(cmd_args, capture_output=True, text=True, check=True, timeout=3)
            if raw_path:
                base_name = os.path.basename(raw_path)
                name = f"{base_name} ({raw_path})"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    except Exception:
        pass
    return name

def find_processes_on_port(port: int) -> List[Dict[str, Any]]:
    process_details = []
    pids_only: List[int] = []
    system = platform.system()
    command_pid = ""
    try:
        if system == "Linux" or system == "Darwin":
            command_pid = f"lsof -ti tcp:{port} -sTCP:LISTEN"
            process = subprocess.Popen(command_pid, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, universal_newlines=True, close_fds=True)
            stdout_pid, _ = process.communicate(timeout=5)
            if process.returncode == 0 and stdout_pid:
                pids_only = [int(p) for p in stdout_pid.strip().splitlines() if p.isdigit()]
        elif system == "Windows":
            command_pid = 'netstat -ano -p TCP'
            process = subprocess.Popen(command_pid, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW)
            stdout_pid, _ = process.communicate(timeout=10)
            if process.returncode == 0 and stdout_pid:
                for line in stdout_pid.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 5 and parts[0].upper() == 'TCP':
                        if parts[3].upper() != 'LISTENING':
                            continue
                        local_address_full = parts[1]
                        try:
                            last_colon_idx = local_address_full.rfind(':')
                            if last_colon_idx == -1:
                                continue
                            extracted_port_str = local_address_full[last_colon_idx+1:]
                            if extracted_port_str.isdigit() and int(extracted_port_str) == port:
                                pid_str = parts[4]
                                if pid_str.isdigit():
                                    pids_only.append(int(pid_str))
                        except (ValueError, IndexError):
                            continue
                pids_only = list(set(pids_only))
    except Exception:
        pass
    for pid_val in pids_only:
        name = get_process_name_by_pid(pid_val)
        process_details.append({"pid": pid_val, "name": name})
    return process_details

def kill_process_pid(pid: int) -> bool:
    system = platform.system()
    success = False
    logger.info(f"Attempting to kill PID {pid} with normal privileges on {system}")
    try:
        if system == "Linux" or system == "Darwin":
            # 1. Attempt SIGTERM (best effort)
            logger.debug(f"Sending SIGTERM to PID {pid}")
            subprocess.run(["kill", "-TERM", str(pid)], capture_output=True, text=True, timeout=3) # check=False
            time.sleep(0.5)

            # 2. Check if process is gone (or if we lack permission to check)
            try:
                logger.debug(f"Checking PID {pid} with kill -0 after SIGTERM attempt")
                # This will raise CalledProcessError if process is gone OR user lacks permission for kill -0
                subprocess.run(["kill", "-0", str(pid)], check=True, capture_output=True, text=True, timeout=1)

                # If kill -0 succeeded, process is still alive and we have permission to signal it.
                # 3. Attempt SIGKILL
                logger.info(f"PID {pid} still alive after SIGTERM attempt (kill -0 succeeded). Sending SIGKILL.")
                subprocess.run(["kill", "-KILL", str(pid)], check=True, capture_output=True, text=True, timeout=3) # Raises on perm error for SIGKILL

                # 4. Verify with kill -0 again that it's gone
                time.sleep(0.1)
                logger.debug(f"Verifying PID {pid} with kill -0 after SIGKILL attempt")
                try:
                    subprocess.run(["kill", "-0", str(pid)], check=True, capture_output=True, text=True, timeout=1)
                    # If kill -0 still succeeds, SIGKILL failed to terminate it or it's unkillable
                    logger.warning(f"PID {pid} still alive even after SIGKILL was sent and did not error.")
                    success = False
                except subprocess.CalledProcessError as e_final_check:
                    # kill -0 failed, means process is gone. Check stderr for "No such process".
                    if e_final_check.stderr and "no such process" in e_final_check.stderr.lower():
                        logger.info(f"PID {pid} successfully terminated with SIGKILL (confirmed by final kill -0).")
                        success = True
                    else:
                        # kill -0 failed for other reason (e.g. perms, though unlikely if SIGKILL 'succeeded')
                        logger.warning(f"Final kill -0 check for PID {pid} failed unexpectedly. Stderr: {e_final_check.stderr}")
                        success = False # Unsure, so treat as failure for normal kill

            except subprocess.CalledProcessError as e:
                # This block is reached if initial `kill -0` fails, or `kill -KILL` fails.
                # `e` is the error from the *first* command that failed with check=True in the try block.
                if e.stderr and "no such process" in e.stderr.lower():
                    logger.info(f"Process {pid} is gone (kill -0 or kill -KILL reported 'No such process'). SIGTERM might have worked or it was already gone.")
                    success = True
                else:
                    # Failure was likely due to permissions (e.g., "Operation not permitted") or other reasons.
                    # This means normal kill attempt failed.
                    logger.warning(f"Normal kill attempt for PID {pid} failed or encountered permission issue. Stderr from failing cmd: {e.stderr}")
                    success = False

        elif system == "Windows":
            logger.debug(f"Using taskkill for PID {pid} on Windows.")
            result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                logger.info(f"Taskkill for PID {pid} succeeded (rc=0).")
                success = True
            else:
                # Check if process was not found
                output_lower = (result.stdout + result.stderr).lower()
                if "pid" in output_lower and ("not found" in output_lower or "no running instance" in output_lower or ("could not be terminated" in output_lower and "reason: there is no running instance" in output_lower)) :
                    logger.info(f"Taskkill for PID {pid} reported process not found or already terminated.")
                    success = True
                else:
                    logger.warning(f"Taskkill for PID {pid} failed. RC: {result.returncode}. Output: {output_lower}")
                    success = False

    except Exception as e_outer: # Catch any other unexpected exceptions
        logger.error(f"Outer exception in kill_process_pid for PID {pid}: {e_outer}", exc_info=True)
        success = False

    logger.info(f"kill_process_pid for PID {pid} final result: {success}")
    return success

def enhanced_port_check(port, port_name_key=""):
    port_display_name = get_text(f"port_name_{port_name_key}") if port_name_key else ""
    update_status_bar("checking_port_with_name", port_name=port_display_name, port=port)

    if is_port_in_use(port):
        pids_data = find_processes_on_port(port)
        if pids_data:
            pids_info_str_list = []
            for proc_info in pids_data:
                pids_info_str_list.append(f"{proc_info['pid']} ({proc_info['name']})")
            return {"port": port, "name_key": port_name_key, "pids_data": pids_data, "pids_str": ", ".join(pids_info_str_list)}
        else:
            return {"port": port, "name_key": port_name_key, "pids_data": [], "pids_str": get_text("unknown_process_name_placeholder")}
    return None

def check_all_required_ports(ports_to_check: List[Tuple[int, str]]) -> bool:
    occupied_ports_info = []
    for port, port_name_key in ports_to_check:
        result = enhanced_port_check(port, port_name_key)
        if result:
            occupied_ports_info.append(result)

    if not occupied_ports_info:
        update_status_bar("port_check_all_completed")
        return True

    occupied_ports_details_for_msg = []
    for info in occupied_ports_info:
        port_display_name = get_text(f"port_name_{info['name_key']}") if info['name_key'] else ""
        occupied_ports_details_for_msg.append(f"  - {port_display_name} (Port {info['port']}): PID {info['pids_str']} tarafından kullanılıyor")

    details_str = "\n".join(occupied_ports_details_for_msg)

    if messagebox.askyesno(
        get_text("confirm_kill_multiple_ports_title"),
        get_text("confirm_kill_multiple_ports_message", occupied_ports_details=details_str),
        parent=root_widget
    ):
        pids_processed_this_cycle = set() # Tracks PIDs for which kill attempts (normal or admin) have been made in this call

        for info in occupied_ports_info:
            if info['pids_data']:
                for p_data in info['pids_data']:
                    pid = p_data['pid']
                    name = p_data['name']

                    if pid in pids_processed_this_cycle:
                        continue # Avoid reprocessing a PID if it appeared for multiple ports

                    logger.info(f"Port Check Cleanup: Attempting normal kill for PID {pid} ({name}) on port {info['port']}")
                    normal_kill_ok = kill_process_pid(pid)

                    if normal_kill_ok:
                        logger.info(f"Port Check Cleanup: Normal kill succeeded for PID {pid} ({name})")
                        pids_processed_this_cycle.add(pid)
                    else:
                        logger.warning(f"Port Check Cleanup: Normal kill FAILED for PID {pid} ({name}). Prompting for admin kill.")
                        if messagebox.askyesno(
                            get_text("confirm_stop_pid_admin_title"),
                            get_text("confirm_stop_pid_admin_message", pid=pid, name=name),
                            parent=root_widget
                        ):
                            logger.info(f"Port Check Cleanup: User approved admin kill for PID {pid} ({name}). Attempting.")
                            admin_kill_initiated = kill_process_pid_admin(pid) # Optimistic for macOS
                            if admin_kill_initiated:
                                logger.info(f"Port Check Cleanup: Admin kill attempt for PID {pid} ({name}) initiated (result optimistic: {admin_kill_initiated}).")
                                # We still rely on the final port check, so no success message here.
                            else:
                                logger.warning(f"Port Check Cleanup: Admin kill attempt for PID {pid} ({name}) failed to initiate or was denied by user at OS level.")
                        else:
                            logger.info(f"Port Check Cleanup: User declined admin kill for PID {pid} ({name}).")
                        pids_processed_this_cycle.add(pid) # Mark as processed even if admin declined/failed, to avoid re-prompting in this cycle

        logger.info("Port Check Cleanup: Waiting for 2 seconds for processes to terminate...")
        time.sleep(2)

        still_occupied_after_cleanup = False
        for info in occupied_ports_info: # Re-check all originally occupied ports
            if is_port_in_use(info['port']):
                port_display_name = get_text(f"port_name_{info['name_key']}") if info['name_key'] else str(info['port'])
                logger.warning(f"Port Check Cleanup: Port {port_display_name} ({info['port']}) is still in use after cleanup attempts.")
                still_occupied_after_cleanup = True
                break

        if not still_occupied_after_cleanup:
            messagebox.showinfo(get_text("info_title"), get_text("all_ports_cleared_success"), parent=root_widget)
            update_status_bar("port_check_all_completed")
            return True
        else:
            messagebox.showwarning(get_text("warning_title"), get_text("some_ports_still_in_use"), parent=root_widget)
            return False
    else:
        update_status_bar("port_check_user_declined_cleanup")
        return False

def _update_active_auth_display():
    """GUI'de gösterilen etkin kimlik doğrulama dosyası bilgisini günceller"""
    if not active_auth_file_display_var or not root_widget:
        return

    if not ENABLE_QWEN_LOGIN_SUPPORT:
        active_auth_file_display_var.set(get_text("current_auth_file_none"))
        return

    active_files = [f for f in os.listdir(ACTIVE_AUTH_DIR) if f.lower().endswith('.json')]
    if active_files:
        # Genellikle active dizininde yalnızca bir dosya olur; yine de ilkini al
        active_file_name = sorted(active_files)[0]
        active_auth_file_display_var.set(get_text("current_auth_file_selected_format", file=active_file_name))
    else:
        active_auth_file_display_var.set(get_text("current_auth_file_none"))


def is_valid_auth_filename(filename: str) -> bool:
    """Checks if the filename is valid for an auth file."""
    if not filename:
        return False
    # Corresponds to LANG_TEXTS["invalid_auth_filename_warn"]
    return bool(re.match(r"^[a-zA-Z0-9_-]+$", filename))


def manage_auth_files_gui():
    if not ENABLE_QWEN_LOGIN_SUPPORT:
        messagebox.showinfo(get_text("auth_disabled_title"), get_text("auth_disabled_message"), parent=root_widget)
        return

    if not os.path.exists(AUTH_PROFILES_DIR): # Kök dizini kontrol et
        messagebox.showerror(get_text("error_title"), get_text("auth_dirs_missing"), parent=root_widget)
        return

    # active ve saved dizinlerinin var olduğundan emin ol, yoksa oluştur
    os.makedirs(ACTIVE_AUTH_DIR, exist_ok=True)
    os.makedirs(SAVED_AUTH_DIR, exist_ok=True)

    auth_window = tk.Toplevel(root_widget)
    auth_window.title(get_text("auth_manager_title"))
    auth_window.geometry("550x300")
    auth_window.resizable(True, True)

    # Dosyaları tara
    all_auth_files = set()
    for dir_path in [AUTH_PROFILES_DIR, ACTIVE_AUTH_DIR, SAVED_AUTH_DIR]:
        if os.path.exists(dir_path):
            for f in os.listdir(dir_path):
                if f.lower().endswith('.json') and os.path.isfile(os.path.join(dir_path, f)):
                    all_auth_files.add(f)

    sorted_auth_files = sorted(list(all_auth_files))

    ttk.Label(auth_window, text=get_text("saved_auth_files_label")).pack(pady=5)

    files_frame = ttk.Frame(auth_window)
    files_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    files_listbox = None
    if sorted_auth_files:
        files_listbox = tk.Listbox(files_frame, selectmode=tk.SINGLE)
        files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        files_scrollbar = ttk.Scrollbar(files_frame, command=files_listbox.yview)
        files_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        files_listbox.config(yscrollcommand=files_scrollbar.set)
        for file_name in sorted_auth_files:
            files_listbox.insert(tk.END, file_name)
    else:
        no_files_label = ttk.Label(files_frame, text=get_text("no_saved_auth_files"), anchor="center")
        no_files_label.pack(pady=10, fill="both", expand=True)

    def activate_selected_file():
        if files_listbox is None or not files_listbox.curselection():
            messagebox.showwarning(get_text("warning_title"), get_text("no_file_selected"), parent=auth_window)
            return

        selected_file_name = files_listbox.get(files_listbox.curselection()[0])
        source_path = None
        for dir_path in [SAVED_AUTH_DIR, ACTIVE_AUTH_DIR, AUTH_PROFILES_DIR]:
            potential_path = os.path.join(dir_path, selected_file_name)
            if os.path.exists(potential_path):
                source_path = potential_path
                break

        if not source_path:
            messagebox.showerror(get_text("error_title"), f"Kaynak dosya {selected_file_name} bulunamadı!", parent=auth_window)
            return

        try:
            for existing_file in os.listdir(ACTIVE_AUTH_DIR):
                if existing_file.lower().endswith('.json'):
                    os.remove(os.path.join(ACTIVE_AUTH_DIR, existing_file))

            import shutil
            dest_path = os.path.join(ACTIVE_AUTH_DIR, selected_file_name)
            shutil.copy2(source_path, dest_path)
            messagebox.showinfo(get_text("info_title"), get_text("auth_file_activated", file=selected_file_name), parent=auth_window)
            _update_active_auth_display()
            auth_window.destroy()
        except Exception as e:
            messagebox.showerror(get_text("error_title"), get_text("error_activating_file", file=selected_file_name, error=str(e)), parent=auth_window)
            _update_active_auth_display()

    def deactivate_auth_file():
       if messagebox.askyesno(get_text("confirm_deactivate_title"), get_text("confirm_deactivate_message"), parent=auth_window):
           try:
               for existing_file in os.listdir(ACTIVE_AUTH_DIR):
                   if existing_file.lower().endswith('.json'):
                       os.remove(os.path.join(ACTIVE_AUTH_DIR, existing_file))
               messagebox.showinfo(get_text("info_title"), get_text("auth_deactivated_success"), parent=auth_window)
               _update_active_auth_display()
               auth_window.destroy()
           except Exception as e:
               messagebox.showerror(get_text("error_title"), get_text("error_deactivating_auth", error=str(e)), parent=auth_window)
               _update_active_auth_display()

    buttons_frame = ttk.Frame(auth_window)
    buttons_frame.pack(fill=tk.X, padx=10, pady=10)

    btn_activate = ttk.Button(buttons_frame, text=get_text("activate_selected_btn"), command=activate_selected_file)
    btn_activate.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    if files_listbox is None:
        btn_activate.config(state=tk.DISABLED)

    ttk.Button(buttons_frame, text=get_text("deactivate_btn"), command=deactivate_auth_file).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    ttk.Button(buttons_frame, text=get_text("create_new_auth_btn"), command=lambda: create_new_auth_file_gui(auth_window)).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
    ttk.Button(buttons_frame, text=get_text("cancel_btn"), command=auth_window.destroy).pack(side=tk.RIGHT, padx=5)

def get_active_auth_json_path_for_launch() -> Optional[str]:
    """Başlatma komutu için kullanılacak --active-auth-json parametresinin değerini döndürür"""
    active_files = [f for f in os.listdir(ACTIVE_AUTH_DIR) if f.lower().endswith('.json') and os.path.isfile(os.path.join(ACTIVE_AUTH_DIR, f))]
    if active_files:
        # Active dizininde dosya varsa alfabetik olarak ilkini kullan
        return os.path.join(ACTIVE_AUTH_DIR, sorted(active_files)[0])
    return None

def build_launch_command(mode, fastapi_port, camoufox_debug_port, stream_port_enabled, stream_port, helper_enabled, helper_endpoint, auto_save_auth: bool = False, save_auth_as: Optional[str] = None):
    cmd = [PYTHON_EXECUTABLE, LAUNCH_CAMOUFOX_PY, f"--{mode}", "--server-port", str(fastapi_port), "--camoufox-debug-port", str(camoufox_debug_port)]

    # Yeni kimlik doğrulaması oluşturulurken mevcut dosyalar yüklenmemeli
    if not auto_save_auth:
        active_auth_path = get_active_auth_json_path_for_launch()
        if active_auth_path:
            cmd.extend(["--active-auth-json", active_auth_path])
            logger.info(f"Kullanılacak kimlik doğrulama dosyası: {active_auth_path}")
        else:
            logger.info("Etkin kimlik doğrulama dosyası bulunamadı; --active-auth-json parametresi gönderilmeyecek.")

    if auto_save_auth:
        cmd.append("--auto-save-auth")
        logger.info("Girişten sonra kimlik doğrulama dosyasını otomatik kaydetmek için --auto-save-auth kullanılacak.")

    if save_auth_as:
        cmd.extend(["--save-auth-as", save_auth_as])
        logger.info(f"Yeni kimlik doğrulama dosyası {save_auth_as}.json olarak kaydedilecek.")

    if stream_port_enabled:
        cmd.extend(["--stream-port", str(stream_port)])
    else:
        cmd.extend(["--stream-port", "0"]) # Açıkça 0 göndererek devre dışı bırak

    if helper_enabled and helper_endpoint:
        cmd.extend(["--helper", helper_endpoint])
    else:
        cmd.extend(["--helper", ""]) # Boş dize göndererek devre dışı bırak

    # Düzeltme: Proxy yapılandırmasını tutarlı şekilde ilet
    # --internal-camoufox-proxy parametresi ortam değişkenlerinden daha yüksek önceliklidir
    if proxy_enabled_var.get():
        proxy_addr = proxy_address_var.get().strip()
        if proxy_addr:
            cmd.extend(["--internal-camoufox-proxy", proxy_addr])
            logger.info(f"GUI'de yapılandırılan proxy kullanılacak: {proxy_addr}")
        else:
            cmd.extend(["--internal-camoufox-proxy", ""])
            logger.info("GUI üzerinden proxy etkin, ancak adres boş; bu nedenle açıkça devre dışı bırakılıyor")
    else:
        cmd.extend(["--internal-camoufox-proxy", ""])
        logger.info("GUI üzerinden proxy etkin değil; açıkça devre dışı bırakılıyor")

    return cmd

# --- GUI'yu oluşturma ve ana mantık bölümüne ait fonksiyon tanımları ---
# (Bu fonksiyonlar yukarıda tanımlanan yardımcıları çağırdığından, tanım sırası önemlidir)

def enqueue_stream_output(stream, stream_name_prefix):
    try:
        for line_bytes in iter(stream.readline, b''):
            if not line_bytes: break
            line = line_bytes.decode(sys.stdout.encoding or 'utf-8', errors='replace')
            if managed_process_info.get("output_area") and root_widget:
                def _update_stream_output(line_to_insert):
                    current_line = line_to_insert
                    if managed_process_info.get("output_area"):
                        managed_process_info["output_area"].config(state=tk.NORMAL)
                        managed_process_info["output_area"].insert(tk.END, current_line)
                        managed_process_info["output_area"].see(tk.END)
                        managed_process_info["output_area"].config(state=tk.DISABLED)
                root_widget.after_idle(_update_stream_output, f"[{stream_name_prefix}] {line}")
            else: print(f"[{stream_name_prefix}] {line.strip()}", flush=True)
    except ValueError: pass
    except Exception: pass
    finally:
        if hasattr(stream, 'close') and not stream.closed: stream.close()

def is_service_running():
    return managed_process_info.get("popen") and \
           managed_process_info["popen"].poll() is None and \
           not managed_process_info.get("fully_detached", False)

def is_any_service_known():
    return managed_process_info.get("popen") is not None

def monitor_process_thread_target():
    popen = managed_process_info.get("popen")
    service_name_key = managed_process_info.get("service_name_key")
    is_detached = managed_process_info.get("fully_detached", False)
    if not popen or not service_name_key: return
    stdout_thread = None; stderr_thread = None
    if popen.stdout:
        stdout_thread = threading.Thread(target=enqueue_stream_output, args=(popen.stdout, "stdout"), daemon=True)
        managed_process_info["stdout_thread"] = stdout_thread
        stdout_thread.start()
    if popen.stderr:
        stderr_thread = threading.Thread(target=enqueue_stream_output, args=(popen.stderr, "stderr"), daemon=True)
        managed_process_info["stderr_thread"] = stderr_thread
        stderr_thread.start()
    popen.wait()
    exit_code = popen.returncode
    if stdout_thread and stdout_thread.is_alive(): stdout_thread.join(timeout=1)
    if stderr_thread and stderr_thread.is_alive(): stderr_thread.join(timeout=1)
    if managed_process_info.get("service_name_key") == service_name_key:
        service_name = get_text(service_name_key)
        if not is_detached:
            if exit_code == 0: update_status_bar("service_stopped_gracefully_status", service_name=service_name)
            else: update_status_bar("service_stopped_exit_code_status", service_name=service_name, code=exit_code)
        managed_process_info["popen"] = None
        managed_process_info["service_name_key"] = None
        managed_process_info["fully_detached"] = False

def get_fastapi_port_from_gui() -> int:
    try:
        port_str = port_entry_var.get()
        if not port_str: messagebox.showwarning(get_text("warning_title"), get_text("enter_valid_port_warn")); return DEFAULT_FASTAPI_PORT
        port = int(port_str)
        if not (1024 <= port <= 65535): raise ValueError("Port out of range")
        return port
    except ValueError:
        messagebox.showwarning(get_text("warning_title"), get_text("enter_valid_port_warn"))
        port_entry_var.set(str(DEFAULT_FASTAPI_PORT))
        return DEFAULT_FASTAPI_PORT

def get_camoufox_debug_port_from_gui() -> int:
    try:
        port_str = camoufox_debug_port_var.get()
        if not port_str:
            camoufox_debug_port_var.set(str(DEFAULT_CAMOUFOX_PORT_GUI))
            return DEFAULT_CAMOUFOX_PORT_GUI
        port = int(port_str)
        if not (1024 <= port <= 65535): raise ValueError("Port out of range")
        return port
    except ValueError:
        messagebox.showwarning(get_text("warning_title"), get_text("enter_valid_port_warn"))
        camoufox_debug_port_var.set(str(DEFAULT_CAMOUFOX_PORT_GUI))
        return DEFAULT_CAMOUFOX_PORT_GUI

# Yapılandırma dosyası yolu
CONFIG_FILE_PATH = os.path.join(SCRIPT_DIR, "gui_config.json")

# Varsayılan yapılandırma - ortam değişkeni varsa onu, yoksa sabit değerleri kullan
DEFAULT_CONFIG = {
    "fastapi_port": DEFAULT_FASTAPI_PORT,
    "camoufox_debug_port": DEFAULT_CAMOUFOX_PORT_GUI,
    "stream_port": int(os.environ.get('GUI_DEFAULT_STREAM_PORT', '3120')),
    "stream_port_enabled": True,
    "helper_endpoint": os.environ.get('GUI_DEFAULT_HELPER_ENDPOINT', ''),
    "helper_enabled": False,
    "proxy_address": os.environ.get('GUI_DEFAULT_PROXY_ADDRESS', 'http://127.0.0.1:7890'),
    "proxy_enabled": False
}

# Yapılandırmayı yükle
def load_config():
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"Yapılandırma dosyası yüklendi: {CONFIG_FILE_PATH}")
                return config
        except Exception as e:
            logger.error(f"Yapılandırma dosyası yüklenemedi: {e}")
    logger.info("Varsayılan yapılandırma kullanılacak")
    return DEFAULT_CONFIG.copy()

# Yapılandırmayı kaydet
def save_config():
    config = {
        "fastapi_port": port_entry_var.get(),
        "camoufox_debug_port": camoufox_debug_port_var.get(),
        "stream_port": stream_port_var.get(),
        "stream_port_enabled": stream_port_enabled_var.get(),
        "helper_endpoint": helper_endpoint_var.get(),
        "helper_enabled": helper_enabled_var.get(),
        "proxy_address": proxy_address_var.get(),
        "proxy_enabled": proxy_enabled_var.get()
    }
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"Yapılandırma kaydedildi: {CONFIG_FILE_PATH}")
    except Exception as e:
        logger.error(f"Yapılandırma kaydedilemedi: {e}")

def custom_yes_no_dialog(title, message, yes_text="Yes", no_text="No"):
    """Creates a custom dialog with specified button texts."""
    dialog = tk.Toplevel(root_widget)
    dialog.title(title)
    dialog.transient(root_widget)
    dialog.grab_set()

    # Center the dialog
    root_x = root_widget.winfo_x()
    root_y = root_widget.winfo_y()
    root_w = root_widget.winfo_width()
    root_h = root_widget.winfo_height()
    dialog.geometry(f"+{root_x + root_w // 2 - 150}+{root_y + root_h // 2 - 50}")


    result = [False] # Use a list to make it mutable inside nested functions

    def on_yes():
        result[0] = True
        dialog.destroy()

    def on_no():
        dialog.destroy()

    ttk.Label(dialog, text=message, wraplength=250).pack(padx=20, pady=20)

    button_frame = ttk.Frame(dialog)
    button_frame.pack(pady=10, padx=10, fill='x')

    yes_button = ttk.Button(button_frame, text=yes_text, command=on_yes)
    yes_button.pack(side=tk.RIGHT, padx=5)

    no_button = ttk.Button(button_frame, text=no_text, command=on_no)
    no_button.pack(side=tk.RIGHT, padx=5)

    yes_button.focus_set()
    dialog.bind("<Return>", lambda event: on_yes())
    dialog.bind("<Escape>", lambda event: on_no())

    root_widget.wait_window(dialog)
    return result[0]

def have_settings_changed() -> bool:
    """GUI ayarlarında değişiklik olup olmadığını kontrol eder"""
    global g_config
    if not g_config:
        return False

    try:
        # Karşılaştırmada tür sorunlarını önlemek için tüm değerleri dizeye veya boole değerine dönüştürün
        if str(g_config.get("fastapi_port", DEFAULT_FASTAPI_PORT)) != port_entry_var.get():
            return True
        if str(g_config.get("camoufox_debug_port", DEFAULT_CAMOUFOX_PORT_GUI)) != camoufox_debug_port_var.get():
            return True
        if str(g_config.get("stream_port", "3120")) != stream_port_var.get():
            return True
        if bool(g_config.get("stream_port_enabled", True)) != stream_port_enabled_var.get():
            return True
        if str(g_config.get("helper_endpoint", "")) != helper_endpoint_var.get():
            return True
        if bool(g_config.get("helper_enabled", False)) != helper_enabled_var.get():
            return True
        if str(g_config.get("proxy_address", "http://127.0.0.1:7890")) != proxy_address_var.get():
            return True
        if bool(g_config.get("proxy_enabled", False)) != proxy_enabled_var.get():
            return True
    except Exception as e:
        logger.warning(f"Ayar değişiklikleri kontrol edilirken hata oluştu: {e}")
        return True # Hata durumunda kaydetmek adına değişiklik var kabul et

    return False

def prompt_to_save_data():
    """Geçerli yapılandırmayı kaydetmek isteyip istemediğinizi soran bir iletişim kutusu gösterir"""
    global g_config
    if custom_yes_no_dialog(
        get_text("confirm_save_settings_title"),
        get_text("confirm_save_settings_message"),
        yes_text=get_text("save_now_btn"),
        no_text=get_text("cancel_btn")
    ):
        save_config()
        g_config = load_config() # Kaydettikten sonra yapılandırmayı yeniden yükle
        messagebox.showinfo(
            get_text("info_title"),
            get_text("settings_saved_success"),
            parent=root_widget
        )

# Proxy ayarları dahil olmak üzere varsayılan değerlere sıfırla
def reset_to_defaults():
    if messagebox.askyesno(get_text("confirm_reset_title"), get_text("confirm_reset_message"), parent=root_widget):
        port_entry_var.set(str(DEFAULT_FASTAPI_PORT))
        camoufox_debug_port_var.set(str(DEFAULT_CAMOUFOX_PORT_GUI))
        stream_port_var.set("3120")
        stream_port_enabled_var.set(True)
        helper_endpoint_var.set("")
        helper_enabled_var.set(False)
        proxy_address_var.set("http://127.0.0.1:7890")
        proxy_enabled_var.set(False)
        messagebox.showinfo(get_text("info_title"), get_text("reset_success"), parent=root_widget)

def _configure_proxy_env_vars() -> Dict[str, str]:
    """
    Proxy ortam değişkenlerini yapılandırır (artık kullanılmıyor, proxy aktarımı öncelikle --internal-camoufox-proxy ile yapılır).
    Geriye dönük uyumluluğu korumak ve durum mesajı göstermek için fonksiyon tutulmuştur.
    """
    proxy_env = {}
    if proxy_enabled_var.get():
        proxy_addr = proxy_address_var.get().strip()
        if proxy_addr:
            # Not: Proxy yapılandırması artık ağırlıklı olarak --internal-camoufox-proxy parametresi ile iletiliyor
            # Ortam değişkenleri yedek çözüm olarak kalıyor ve önceliği düşük
            update_status_bar("proxy_configured_status", proxy_addr=proxy_addr)
        else:
            update_status_bar("proxy_skip_status")
    else:
        update_status_bar("proxy_skip_status")
    return proxy_env

def _launch_process_gui(cmd: List[str], service_name_key: str, env_vars: Optional[Dict[str, str]] = None, force_save_prompt: bool = False):
    global managed_process_info # managed_process_info is now informational for these launches
    service_name = get_text(service_name_key)

    # Clear previous output area for GUI messages, actual process output will be in the new terminal
    if managed_process_info.get("output_area"):
        managed_process_info["output_area"].config(state=tk.NORMAL)
        managed_process_info["output_area"].delete('1.0', tk.END)
        managed_process_info["output_area"].insert(tk.END, f"[INFO] Preparing to launch {service_name} in a new terminal...\\n")
        managed_process_info["output_area"].config(state=tk.DISABLED)

    effective_env = os.environ.copy()
    if env_vars: effective_env.update(env_vars)
    effective_env['PYTHONIOENCODING'] = 'utf-8'

    popen_kwargs: Dict[str, Any] = {"env": effective_env}
    system = platform.system()
    launch_cmd_for_terminal: Optional[List[str]] = None

    # Prepare command string for terminals that take a single command string
    # Ensure correct quoting for arguments with spaces
    cmd_parts_for_string = []
    for part in cmd:
        if " " in part and not (part.startswith('"') and part.endswith('"')):
            cmd_parts_for_string.append(f'"{part}"')
        else:
            cmd_parts_for_string.append(part)
    cmd_str_for_terminal_execution = " ".join(cmd_parts_for_string)


    if system == "Windows":
        # CREATE_NEW_CONSOLE opens a new window.
        # The new process will be a child of this GUI initially, but if python.exe
        # itself handles its lifecycle well, closing GUI might not kill it.
        # To be more robust for independence, one might use 'start' cmd,
        # but simple CREATE_NEW_CONSOLE often works for python scripts.
        # For true independence and GUI not waiting, Popen should be on python.exe directly.
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        launch_cmd_for_terminal = cmd # Direct command
    elif system == "Darwin": # macOS
        # import shlex # Ensure shlex is imported (should be at top of file)

        # Build the shell command string with proper quoting for each argument.
        # The command will first change to SCRIPT_DIR, then execute the python script.
        script_dir_quoted = shlex.quote(SCRIPT_DIR)
        python_executable_quoted = shlex.quote(cmd[0])
        script_path_quoted = shlex.quote(cmd[1])

        args_for_script_quoted = [shlex.quote(arg) for arg in cmd[2:]]

        # Ortam değişkeni ayarları dizesini oluştur
        env_prefix_parts = []
        if env_vars: # env_vars, _configure_proxy_env_vars() fonksiyonundan gelen proxy_env olmalı
            for key, value in env_vars.items():
                if value is not None: # Değerin mevcut ve boş dize olmadığını doğrulayın
                    env_prefix_parts.append(f"{shlex.quote(key)}={shlex.quote(str(value))}")
        env_prefix_str = " ".join(env_prefix_parts)

        # Construct the full shell command to be executed in the new terminal
        shell_command_parts = [
            f"cd {script_dir_quoted}",
            "&&" # Ensure command separation
        ]
        if env_prefix_str:
            shell_command_parts.append(env_prefix_str)

        shell_command_parts.extend([
            python_executable_quoted,
            script_path_quoted
        ])
        shell_command_parts.extend(args_for_script_quoted)
        shell_command_str = " ".join(shell_command_parts)

        # Şimdi, AppleScript çift tırnaklı dizesine gömme için shell_command_str'yi kaçırmalıyız.
        # AppleScript dizelerinde ters eğik çizgi `\\` ve çift tırnak `\"` özel karakterlerdir ve kaçırılmalıdır.
        applescript_arg_escaped = shell_command_str.replace('\\\\', '\\\\\\\\').replace('\"', '\\\\\"')

        # Construct the AppleScript command
        # Düzeltme: AppleEvent işleyicisinin başarısız olmasını önlemek için basitleştirilmiş AppleScript komutu kullanın
        # Karmaşık koşulları önlemek için doğrudan yeni bir pencere oluşturun ve komutu yürütün
        applescript_command = f'''
        tell application "Terminal"
            do script "{applescript_arg_escaped}"
            activate
        end tell
        '''

        launch_cmd_for_terminal = ["osascript", "-e", applescript_command.strip()]
    elif system == "Linux":
        import shutil
        terminal_emulator = shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal") or shutil.which("konsole") or shutil.which("xfce4-terminal") or shutil.which("xterm")
        if terminal_emulator:
            # Construct command ensuring SCRIPT_DIR is CWD for the launched script
            # Some terminals might need `sh -c "cd ... && python ..."`
            # For simplicity, let's try to pass the command directly if possible or via sh -c
            cd_command = f"cd '{SCRIPT_DIR}' && "
            full_command_to_run = cd_command + cmd_str_for_terminal_execution

            if "gnome-terminal" in terminal_emulator or "mate-terminal" in terminal_emulator:
                launch_cmd_for_terminal = [terminal_emulator, "--", "bash", "-c", full_command_to_run + "; exec bash"]
            elif "konsole" in terminal_emulator or "xfce4-terminal" in terminal_emulator or "lxterminal" in terminal_emulator:
                 launch_cmd_for_terminal = [terminal_emulator, "-e", f"bash -c '{full_command_to_run}; exec bash'"]
            elif "xterm" in terminal_emulator: # xterm might need careful quoting
                 launch_cmd_for_terminal = [terminal_emulator, "-hold", "-e", "bash", "-c", f"{full_command_to_run}"]
            else: # Generic x-terminal-emulator
                 launch_cmd_for_terminal = [terminal_emulator, "-e", f"bash -c '{full_command_to_run}; exec bash'"]
        else:
            messagebox.showerror(get_text("error_title"), "Linux için uyumlu bir terminal öykünücüsü bulunamadı (ör. x-terminal-emulator, gnome-terminal, xterm). Hizmet yeni bir terminalde başlatılamıyor.")
            update_status_bar("status_error_starting", service_name=service_name)
            return
    else: # Diğer işletim sistemleri veya belirli terminal başlatma başarısız olursa yedek
        messagebox.showerror(get_text("error_title"), f"{system} işletim sistemi için yeni terminalde başlatma desteklenmiyor.")
        update_status_bar("status_error_starting", service_name=service_name)
        return

    if not launch_cmd_for_terminal: # Yukarıdaki mantık doğruysa bu olmamalı
        messagebox.showerror(get_text("error_title"), f"{system} için terminal başlatma komutu oluşturulamadı.")
        update_status_bar("status_error_starting", service_name=service_name)
        return

    try:
        # Launch the terminal command. This Popen object is for the terminal launcher.
        # The actual Python script is a child of that new terminal.
        logger.info(f"Launching in new terminal with command: {' '.join(launch_cmd_for_terminal)}")
        logger.info(f"Effective environment for new terminal: {effective_env}")

        # For non-Windows, where we launch `osascript` or a terminal emulator,
        # these Popen objects complete quickly.
        # For Windows, `CREATE_NEW_CONSOLE` means the Popen object is for the new python process.
        # However, we are treating all as fire-and-forget for the GUI.
        process = subprocess.Popen(launch_cmd_for_terminal, **popen_kwargs)

        # After successfully launching, prompt to save data if settings have changed or if forced
        if root_widget and (force_save_prompt or have_settings_changed()):
            root_widget.after(200, prompt_to_save_data) # Use a small delay

        # We no longer store this popen object in managed_process_info for direct GUI management
        # as the process is meant to be independent.
        # managed_process_info["popen"] = process
        # managed_process_info["service_name_key"] = service_name_key
        # managed_process_info["fully_detached"] = True

        # No monitoring threads from GUI for these independent processes.
        # managed_process_info["monitor_thread"] = None
        # managed_process_info["stdout_thread"] = None
        # managed_process_info["stderr_thread"] = None

        update_status_bar("info_service_new_terminal")
        if managed_process_info.get("output_area"):
             managed_process_info["output_area"].config(state=tk.NORMAL)
             managed_process_info["output_area"].insert(tk.END, f"[INFO] {get_text('info_service_new_terminal')}\\n")
             managed_process_info["output_area"].insert(tk.END, f"[INFO] {service_name} (PID: {process.pid if system == 'Windows' else 'N/A for terminal launcher'}) should be running in a new window.\\n")
             managed_process_info["output_area"].see(tk.END)
             managed_process_info["output_area"].config(state=tk.DISABLED)

        if root_widget: # Query ports after a delay, as service might take time to start
            root_widget.after(3500, query_port_and_display_pids_gui)

    except FileNotFoundError:
        messagebox.showerror(get_text("error_title"), get_text("script_not_found_error_msgbox", cmd=' '.join(cmd)))
        update_status_bar("status_script_not_found", service_name=service_name)
    except Exception as e:
        messagebox.showerror(get_text("error_title"), f"{service_name} - {get_text('error_title')}: {e}")
        update_status_bar("status_error_starting", service_name=service_name)
        logger.error(f"Error in _launch_process_gui for {service_name}: {e}", exc_info=True)

@debounce_button("start_headed_interactive", 3.0)
def start_headed_interactive_gui():
    launch_params = _get_launch_parameters()
    if not launch_params: return

    if port_auto_check_var.get():
        ports_to_check = [
            (launch_params["fastapi_port"], "fastapi"),
            (launch_params["camoufox_debug_port"], "camoufox_debug")
        ]
        if launch_params["stream_port_enabled"] and launch_params["stream_port"] != 0:
            ports_to_check.append((launch_params["stream_port"], "stream_proxy"))
        if launch_params["helper_enabled"] and launch_params["helper_endpoint"]:
            try:
                pu = urlparse(launch_params["helper_endpoint"])
                if pu.hostname in ("localhost", "127.0.0.1") and pu.port:
                    ports_to_check.append((pu.port, "helper_service"))
            except Exception as e:
                print(f"Helper URL'si ayrıştırılamadı (Başlıklı mod): {e}")
        if not check_all_required_ports(ports_to_check): return

    proxy_env = _configure_proxy_env_vars()
    cmd = build_launch_command(
        "debug",
        launch_params["fastapi_port"],
        launch_params["camoufox_debug_port"],
        launch_params["stream_port_enabled"],
        launch_params["stream_port"],
        launch_params["helper_enabled"],
        launch_params["helper_endpoint"]
    )
    update_status_bar("status_headed_launch")
    _launch_process_gui(cmd, "service_name_headed_interactive", env_vars=proxy_env)

def create_new_auth_file_gui(parent_window):
    """
    Handles the workflow for creating a new authentication file.
    """
    if not ENABLE_QWEN_LOGIN_SUPPORT:
        messagebox.showinfo(get_text("auth_disabled_title"), get_text("auth_disabled_message"), parent=parent_window)
        return

    logger.info("Starting 'create new auth file' workflow.")
    # 1. Prompt for filename first
    filename = None
    while True:
        logger.info("Prompting for filename.")
        filename = simpledialog.askstring(
            get_text("create_new_auth_filename_prompt_title"),
            get_text("create_new_auth_filename_prompt"),
            parent=parent_window
        )
        logger.info(f"User entered: {filename}")
        if filename is None: # User cancelled
            logger.info("User cancelled filename prompt.")
            return
        if is_valid_auth_filename(filename):
            logger.info(f"Filename '{filename}' is valid.")
            break
        else:
            logger.warning(f"Filename '{filename}' is invalid.")
            messagebox.showwarning(
                get_text("warning_title"),
                get_text("invalid_auth_filename_warn"),
                parent=parent_window
            )

    logger.info("Preparing to show confirmation dialog.")
    # 2. Show instructions and get final confirmation
    try:
        title = get_text("create_new_auth_instructions_title")
        logger.info(f"Confirmation title: '{title}'")
        message = get_text("create_new_auth_instructions_message_revised", filename=filename)
        logger.info(f"Confirmation message: '{message}'")

        if messagebox.askokcancel(
            title,
            message,
            parent=parent_window
        ):
            logger.info("User confirmed. Proceeding to launch.")
            # YENİ: Tarayıcı işleminin Enter tuşu için beklememesi için bayrağı ayarlayın.
            os.environ["SUPPRESS_LOGIN_WAIT"] = "1"
            parent_window.destroy()
            launch_params = _get_launch_parameters()
            if not launch_params:
                logger.error("Başlatma parametreleri alınamadı.")
                return
            if port_auto_check_var.get():
                if not check_all_required_ports([(launch_params["camoufox_debug_port"], "camoufox_debug")]):
                    return
            proxy_env = _configure_proxy_env_vars()
            cmd = build_launch_command(
                "debug",
                launch_params["fastapi_port"],
                launch_params["camoufox_debug_port"],
                launch_params["stream_port_enabled"],
                launch_params["stream_port"],
                launch_params["helper_enabled"],
                launch_params["helper_endpoint"],
                auto_save_auth=True,
                save_auth_as=filename  # Using the provided filename from the dialog.
            )
            update_status_bar("status_headed_launch")
            _launch_process_gui(cmd, "service_name_auth_creation", env_vars=proxy_env, force_save_prompt=True)
        else:
            logger.info("User cancelled the auth creation process.")
    except Exception as e:
        logger.error(f"Error in create_new_auth_file_gui: {e}", exc_info=True)
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")

@debounce_button("start_headless", 3.0)
def start_headless_gui():
    launch_params = _get_launch_parameters()
    if not launch_params: return

    if port_auto_check_var.get():
        ports_to_check = [
            (launch_params["fastapi_port"], "fastapi"),
            (launch_params["camoufox_debug_port"], "camoufox_debug")
        ]
        if launch_params["stream_port_enabled"] and launch_params["stream_port"] != 0:
            ports_to_check.append((launch_params["stream_port"], "stream_proxy"))
        if launch_params["helper_enabled"] and launch_params["helper_endpoint"]:
            try:
                pu = urlparse(launch_params["helper_endpoint"])
                if pu.hostname in ("localhost", "127.0.0.1") and pu.port:
                    ports_to_check.append((pu.port, "helper_service"))
            except Exception as e:
                print(f"Helper URL'si ayrıştırılamadı (Başlıksız mod): {e}")
        if not check_all_required_ports(ports_to_check): return

    proxy_env = _configure_proxy_env_vars()
    cmd = build_launch_command(
        "headless",
        launch_params["fastapi_port"],
        launch_params["camoufox_debug_port"],
        launch_params["stream_port_enabled"],
        launch_params["stream_port"],
        launch_params["helper_enabled"],
        launch_params["helper_endpoint"]
    )
    update_status_bar("status_headless_launch")
    _launch_process_gui(cmd, "service_name_headless", env_vars=proxy_env)

@debounce_button("start_virtual_display", 3.0)
def start_virtual_display_gui():
    if platform.system() != "Linux":
        messagebox.showwarning(get_text("warning_title"), "Sanal ekran modu sadece Linux'ta desteklenir.")
        return

    launch_params = _get_launch_parameters()
    if not launch_params: return

    if port_auto_check_var.get():
        ports_to_check = [
            (launch_params["fastapi_port"], "fastapi"),
            (launch_params["camoufox_debug_port"], "camoufox_debug")
        ]
        if launch_params["stream_port_enabled"] and launch_params["stream_port"] != 0:
            ports_to_check.append((launch_params["stream_port"], "stream_proxy"))
        if launch_params["helper_enabled"] and launch_params["helper_endpoint"]:
            try:
                pu = urlparse(launch_params["helper_endpoint"])
                if pu.hostname in ("localhost", "127.0.0.1") and pu.port:
                    ports_to_check.append((pu.port, "helper_service"))
            except Exception as e:
                print(f"Helper URL'si ayrıştırılamadı (Sanal ekran modu): {e}")
        if not check_all_required_ports(ports_to_check): return

    proxy_env = _configure_proxy_env_vars()
    cmd = build_launch_command(
        "virtual-display",
        launch_params["fastapi_port"],
        launch_params["camoufox_debug_port"],
        launch_params["stream_port_enabled"],
        launch_params["stream_port"],
        launch_params["helper_enabled"],
        launch_params["helper_endpoint"]
    )
    update_status_bar("status_virtual_display_launch")
    _launch_process_gui(cmd, "service_name_virtual_display", env_vars=proxy_env)
# --- LLM Sahte Hizmet Yönetimi ---

def is_llm_service_running() -> bool:
    """Yerel LLM sahte hizmetinin çalışıp çalışmadığını kontrol eder"""
    return llm_service_process_info.get("popen") and \
           llm_service_process_info["popen"].poll() is None


def monitor_llm_process_thread_target():
    """LLM hizmet işlemini izler, çıktıyı yakalar ve durumu günceller"""
    popen = llm_service_process_info.get("popen")
    service_name_key = llm_service_process_info.get("service_name_key") # "llm_service_name_key"
    output_area = managed_process_info.get("output_area") # Ana çıktı alanını kullan

    if not popen or not service_name_key or not output_area:
        logger.error("LLM monitor thread: Popen, service_name_key, or output_area is None.")
        return

    service_name = get_text(service_name_key)
    logger.info(f"Starting monitor thread for {service_name} (PID: {popen.pid})")

    # stdout/stderr redirection
    if popen.stdout:
        llm_service_process_info["stdout_thread"] = threading.Thread(
            target=enqueue_stream_output, args=(popen.stdout, f"{service_name}-stdout"), daemon=True
        )
        llm_service_process_info["stdout_thread"].start()

    if popen.stderr:
        llm_service_process_info["stderr_thread"] = threading.Thread(
            target=enqueue_stream_output, args=(popen.stderr, f"{service_name}-stderr"), daemon=True
        )
        llm_service_process_info["stderr_thread"].start()

    popen.wait() # Wait for the process to terminate
    exit_code = popen.returncode
    logger.info(f"{service_name} (PID: {popen.pid}) terminated with exit code {exit_code}.")

    if llm_service_process_info.get("stdout_thread") and llm_service_process_info["stdout_thread"].is_alive():
        llm_service_process_info["stdout_thread"].join(timeout=1)
    if llm_service_process_info.get("stderr_thread") and llm_service_process_info["stderr_thread"].is_alive():
        llm_service_process_info["stderr_thread"].join(timeout=1)

    # Update status only if this was the process we were tracking
    if llm_service_process_info.get("popen") == popen:
        update_status_bar("status_llm_stopped")
        llm_service_process_info["popen"] = None
        llm_service_process_info["monitor_thread"] = None
        llm_service_process_info["stdout_thread"] = None
        llm_service_process_info["stderr_thread"] = None

def _actually_launch_llm_service():
    """llm.py betiğini gerçekten başlatır"""
    global llm_service_process_info
    service_name_key = "llm_service_name_key"
    service_name = get_text(service_name_key)
    output_area = managed_process_info.get("output_area")

    if not output_area:
        logger.error("Cannot launch LLM service: Main output area is not available.")
        update_status_bar("status_error_starting", service_name=service_name)
        return

    llm_script_path = os.path.join(SCRIPT_DIR, LLM_PY_FILENAME)
    if not os.path.exists(llm_script_path):
        messagebox.showerror(get_text("error_title"), get_text("startup_script_not_found_msgbox", script=LLM_PY_FILENAME))
        update_status_bar("status_script_not_found", service_name=service_name)
        return

    # Get the main server port from GUI to pass to llm.py
    main_server_port = get_fastapi_port_from_gui() # Ensure this function is available and returns the correct port

    cmd = [PYTHON_EXECUTABLE, llm_script_path, f"--main-server-port={main_server_port}"]
    logger.info(f"Attempting to launch LLM service with command: {' '.join(cmd)}")

    try:
        # Clear previous LLM service output if any, or add a header
        output_area.config(state=tk.NORMAL)
        output_area.insert(tk.END, f"--- Starting {service_name} ---\n")
        output_area.config(state=tk.DISABLED)

        effective_env = os.environ.copy()
        effective_env['PYTHONUNBUFFERED'] = '1' # Ensure unbuffered output for real-time logging
        effective_env['PYTHONIOENCODING'] = 'utf-8'

        popen = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False, # Read as bytes for enqueue_stream_output
            cwd=SCRIPT_DIR,
            env=effective_env,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )
        llm_service_process_info["popen"] = popen
        llm_service_process_info["service_name_key"] = service_name_key

        update_status_bar("status_llm_starting", pid=popen.pid)
        logger.info(f"{service_name} started with PID: {popen.pid}")

        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor_llm_process_thread_target, daemon=True)
        llm_service_process_info["monitor_thread"] = monitor_thread
        monitor_thread.start()

    except FileNotFoundError:
        messagebox.showerror(get_text("error_title"), get_text("script_not_found_error_msgbox", cmd=' '.join(cmd)))
        update_status_bar("status_script_not_found", service_name=service_name)
        logger.error(f"FileNotFoundError when trying to launch LLM service: {cmd}")
    except Exception as e:
        messagebox.showerror(get_text("error_title"), f"{service_name} - {get_text('error_title')}: {e}")
        update_status_bar("status_error_starting", service_name=service_name)
        logger.error(f"Exception when launching LLM service: {e}", exc_info=True)
        llm_service_process_info["popen"] = None # Ensure it's cleared on failure

def _check_llm_backend_and_launch_thread():
    """LLM arka uç hizmetini kontrol eder (dinamik port) ve başarılı olursa llm.py'yi başlatır"""
    # GUI'den mevcut FastAPI portunu alın
    # port_entry_var farklı bir iş parçacığından erişilebileceği için bu, kontrolden hemen önce
    # bu iş parçacığı içinde çağrılması gerekir.
    # However, Tkinter GUI updates should ideally be done from the main thread.
    # For reading a StringVar, it's generally safe.
    current_fastapi_port = get_fastapi_port_from_gui()

    # Update status bar and logger with the dynamic port
    # For status bar updates from a thread, it's better to use root_widget.after or a queue,
    # but for simplicity in this context, direct update_status_bar call is used.
    # Ensure update_status_bar is thread-safe or schedules GUI updates.
    # The existing update_status_bar uses root_widget.after_idle, which is good.

    # Dynamically create the message keys for status bar to include the port
    backend_check_msg_key = "status_llm_backend_check" # Original key
    backend_ok_msg_key = "status_llm_backend_ok_starting"
    backend_fail_msg_key = "status_llm_backend_fail"

    # It's better to pass the port as a parameter to get_text if the LANG_TEXTS are updated
    # For now, we'll just log the dynamic port separately.
    update_status_bar(backend_check_msg_key) # Still uses the generic message
    logger.info(f"Checking LLM backend service at localhost:{current_fastapi_port}...")

    backend_ok = False
    try:
        with socket.create_connection(("localhost", current_fastapi_port), timeout=3) as sock:
            backend_ok = True
        logger.info(f"LLM backend service (localhost:{current_fastapi_port}) is responsive.")
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        logger.warning(f"LLM backend service (localhost:{current_fastapi_port}) not responding: {e}")
        backend_ok = False

    if root_widget: # Ensure GUI is still there
        if backend_ok:
            update_status_bar(backend_ok_msg_key, port=current_fastapi_port) # Pass port to fill placeholder
            _actually_launch_llm_service() # This already gets the port via get_fastapi_port_from_gui()
        else:
            # Update status bar with the dynamic port for failure message
            update_status_bar(backend_fail_msg_key, port=current_fastapi_port)

            # Show warning messagebox with the dynamic port
            # The status bar is already updated by update_status_bar,
            # so no need to manually set process_status_text_var or write to output_area here again for the same message.
            # The update_status_bar function handles writing to the output_area if configured.
            messagebox.showwarning(
                get_text("warning_title"),
                get_text(backend_fail_msg_key, port=current_fastapi_port), # Use get_text with port for the messagebox
                parent=root_widget
            )

def start_llm_service_gui():
    """GUI komutu: Yerel LLM sahte hizmetini başlatır"""
    if is_llm_service_running():
        pid = llm_service_process_info["popen"].pid
        update_status_bar("status_llm_already_running", pid=pid)
        messagebox.showinfo(get_text("info_title"), get_text("status_llm_already_running", pid=pid), parent=root_widget)
        return

    # Run the check and actual launch in a new thread to keep GUI responsive
    # The check itself can take a few seconds if the port is unresponsive.
    threading.Thread(target=_check_llm_backend_and_launch_thread, daemon=True).start()
def stop_llm_service_gui():
    """GUI komutu: Yerel LLM sahte hizmetini durdurur"""
    service_name = get_text(llm_service_process_info.get("service_name_key", "llm_service_name_key"))
    popen = llm_service_process_info.get("popen")


    if not popen or popen.poll() is not None:
        update_status_bar("status_llm_not_running")
        # messagebox.showinfo(get_text("info_title"), get_text("status_llm_not_running"), parent=root_widget)
        return

    if messagebox.askyesno(get_text("confirm_stop_llm_title"), get_text("confirm_stop_llm_message"), parent=root_widget):
        logger.info(f"Attempting to stop {service_name} (PID: {popen.pid})")
        update_status_bar("status_stopping_service", service_name=service_name, pid=popen.pid)

        try:
            # Attempt graceful termination first
            if platform.system() == "Windows":
                # Windows'ta CREATE_NO_WINDOW ile oluşturulan bir Popen nesnesine SIGINT göndermek
                # Flask uygulamaları için beklendiği gibi çalışmayabilir. taskkill daha güvenilirdir.
                # Ctrl+C'yi konsola göndermeyi deneyebiliriz ama llm.py basittir.
                # Flask için doğrudan popen.terminate() veya popen.kill() genellikle kullanılır.
                logger.info(f"Windows'ta {service_name} (PID: {popen.pid}) işlemine SIGTERM/terminate gönderiliyor.")
                popen.terminate() # Unix'te SIGTERM, Windows'ta TerminateProcess gönderir
            else: # Linux/macOS
                logger.info(f"{platform.system()} üzerinde {service_name} (PID: {popen.pid}) işlemine SIGINT gönderiliyor.")
                popen.send_signal(signal.SIGINT)

            # Wait for a short period for graceful shutdown
            try:
                popen.wait(timeout=5) # Wait up to 5 seconds
                logger.info(f"{service_name} (PID: {popen.pid}) terminated gracefully after signal.")
                update_status_bar("status_llm_stopped")
            except subprocess.TimeoutExpired:
                logger.warning(f"{service_name} (PID: {popen.pid}) did not terminate after signal. Forcing kill.")
                popen.kill() # Force kill
                popen.wait(timeout=2) # Wait for kill to take effect
                update_status_bar("status_llm_stopped") # Assume killed
                logger.info(f"{service_name} (PID: {popen.pid}) was force-killed.")

        except Exception as e:
            logger.error(f"Error stopping {service_name} (PID: {popen.pid}): {e}", exc_info=True)
            update_status_bar("status_llm_stop_error")
            messagebox.showerror(get_text("error_title"), f"Error stopping {service_name}: {e}", parent=root_widget)
        finally:
            # Ensure threads are joined and resources cleaned up, even if already done by monitor
            if llm_service_process_info.get("stdout_thread") and llm_service_process_info["stdout_thread"].is_alive():
                llm_service_process_info["stdout_thread"].join(timeout=0.5)
            if llm_service_process_info.get("stderr_thread") and llm_service_process_info["stderr_thread"].is_alive():
                llm_service_process_info["stderr_thread"].join(timeout=0.5)

            llm_service_process_info["popen"] = None
            llm_service_process_info["monitor_thread"] = None
            llm_service_process_info["stdout_thread"] = None
            llm_service_process_info["stderr_thread"] = None

            # Clear related output from the main log area or add a "stopped" message
            output_area = managed_process_info.get("output_area")
            if output_area:
                output_area.config(state=tk.NORMAL)
                output_area.insert(tk.END, f"--- {service_name} stopped ---\n")
                output_area.see(tk.END)
                output_area.config(state=tk.DISABLED)
    else:
        logger.info(f"User cancelled stopping {service_name}.")

# --- End LLM Mock Service Management ---

def query_port_and_display_pids_gui():
    ports_to_query_info = []
    ports_desc_list = []

    # 1. FastAPI Port
    fastapi_port = get_fastapi_port_from_gui()
    ports_to_query_info.append({"port": fastapi_port, "type_key": "port_name_fastapi", "type_name": get_text("port_name_fastapi")})
    ports_desc_list.append(f"{get_text('port_name_fastapi')}:{fastapi_port}")

    # 2. Camoufox Debug Port
    camoufox_port = get_camoufox_debug_port_from_gui()
    ports_to_query_info.append({"port": camoufox_port, "type_key": "port_name_camoufox_debug", "type_name": get_text("port_name_camoufox_debug")})
    ports_desc_list.append(f"{get_text('port_name_camoufox_debug')}:{camoufox_port}")

    # 3. Stream Proxy Port (if enabled)
    if stream_port_enabled_var.get():
        try:
            stream_p_val_str = stream_port_var.get().strip()
            stream_p = int(stream_p_val_str) if stream_p_val_str else 0 # Default to 0 if empty, meaning disabled
            if stream_p != 0 and not (1024 <= stream_p <= 65535):
                 messagebox.showwarning(get_text("warning_title"), get_text("stream_port_out_of_range"), parent=root_widget)
                 # Optionally, do not query this port or handle as error
            elif stream_p != 0 : # Only query if valid and non-zero
                ports_to_query_info.append({"port": stream_p, "type_key": "port_name_stream_proxy", "type_name": get_text("port_name_stream_proxy")})
                ports_desc_list.append(f"{get_text('port_name_stream_proxy')}:{stream_p}")
        except ValueError:
            messagebox.showwarning(get_text("warning_title"), get_text("stream_port_out_of_range") + " (geçerli bir sayı değil)", parent=root_widget)


    update_status_bar("querying_ports_status", ports_desc=", ".join(ports_desc_list))

    if pid_listbox_widget and pid_list_lbl_frame_ref:
        pid_listbox_widget.delete(0, tk.END)
        pid_list_lbl_frame_ref.config(text=get_text("pids_on_multiple_ports_label")) # Update title

        found_any_process = False
        for port_info in ports_to_query_info:
            current_port = port_info["port"]
            port_type_name = port_info["type_name"]

            processes_on_current_port = find_processes_on_port(current_port)
            if processes_on_current_port:
                found_any_process = True
                for proc_info in processes_on_current_port:
                    pid_display_info = f"{proc_info['pid']} - {proc_info['name']}"
                    display_text = get_text("port_query_result_format",
                                            port_type=port_type_name,
                                            port_num=current_port,
                                            pid_info=pid_display_info)
                    pid_listbox_widget.insert(tk.END, display_text)
            else:
                display_text = get_text("port_not_in_use_format",
                                        port_type=port_type_name,
                                        port_num=current_port)
                pid_listbox_widget.insert(tk.END, display_text)

        if not found_any_process and not any(find_processes_on_port(p["port"]) for p in ports_to_query_info): # Recheck if all are empty
             # If after checking all, still no processes, we can add a general "no pids found on queried ports"
             # but the per-port "not in use" message is usually clearer.
             pass # Individual messages already cover this.
    else:
        logger.error("pid_listbox_widget or pid_list_lbl_frame_ref is None in query_port_and_display_pids_gui")

def _perform_proxy_test_single(proxy_address: str, test_url: str, timeout: int = 15) -> Tuple[bool, str, int]:
    """
    Tek seferlik proxy testi denemesi
    Returns (success_status, message_or_error_string, status_code).
    """
    proxies = {
        "http": proxy_address,
        "https": proxy_address,
    }
    try:
        logger.info(f"Testing proxy {proxy_address} with URL {test_url} (timeout: {timeout}s)")
        response = requests.get(test_url, proxies=proxies, timeout=timeout, allow_redirects=True)
        status_code = response.status_code

        # HTTP durum kodunu kontrol et
        if 200 <= status_code < 300:
            logger.info(f"Proxy test to {test_url} via {proxy_address} successful. Status: {status_code}")
            return True, get_text("proxy_test_success", url=test_url), status_code
        elif status_code == 503:
            # 503 Service Unavailable - muhtemelen geçici bir sorun
            logger.warning(f"Proxy test got 503 Service Unavailable from {test_url} via {proxy_address}")
            return False, f"HTTP {status_code}: Service Temporarily Unavailable", status_code
        elif 400 <= status_code < 500:
            # 4xx istemci hataları
            logger.warning(f"Proxy test got client error {status_code} from {test_url} via {proxy_address}")
            return False, f"HTTP {status_code}: Client Error", status_code
        elif 500 <= status_code < 600:
            # 5xx sunucu hataları
            logger.warning(f"Proxy test got server error {status_code} from {test_url} via {proxy_address}")
            return False, f"HTTP {status_code}: Server Error", status_code
        else:
            logger.warning(f"Proxy test got unexpected status {status_code} from {test_url} via {proxy_address}")
            return False, f"HTTP {status_code}: Unexpected Status", status_code
except requests.exceptions.ProxyError as e:
    logger.error(f"{proxy_address} üzerinden {test_url} bağlantısı sırasında ProxyError: {e}")
    return False, f"Proxy Hatası: {e}", 0
except requests.exceptions.ConnectTimeout as e:
    logger.error(f"{proxy_address} üzerinden {test_url} bağlantısı sırasında ConnectTimeout: {e}")
    return False, f"Bağlantı Zaman Aşımı: {e}", 0
except requests.exceptions.ReadTimeout as e:
    logger.error(f"{proxy_address} üzerinden {test_url} bağlantısı sırasında ReadTimeout: {e}")
    return False, f"Okuma Zaman Aşımı: {e}", 0
except requests.exceptions.SSLError as e:
    logger.error(f"{proxy_address} üzerinden {test_url} bağlantısı sırasında SSLError: {e}")
    return False, f"SSL Hatası: {e}", 0
except requests.exceptions.RequestException as e:
    logger.error(f"{proxy_address} üzerinden {test_url} bağlantısı sırasında RequestException: {e}")
    return False, str(e), 0
except Exception as e: # Beklenmeyen diğer hataları yakalayın
    logger.error(f"{proxy_address} üzerinden {test_url} proxy testi sırasında beklenmeyen hata: {e}", exc_info=True)
    return False, f"Beklenmeyen hata: {e}", 0


def _perform_proxy_test(proxy_address: str, test_url: str) -> Tuple[bool, str]:
    """
    Yenilenmiş proxy test fonksiyonu; yeniden deneme mekanizması ve yedek URL içerir
    Returns (success_status, message_or_error_string).
    """
    max_attempts = 3
    backup_url = LANG_TEXTS["proxy_test_url_backup"]
    urls_to_try = [test_url]

    # Ana URL yedek URL ile aynı değilse listeye yedeği ekle
    if test_url != backup_url:
        urls_to_try.append(backup_url)

    for url_index, current_url in enumerate(urls_to_try):
        if url_index > 0:
            logger.info(f"Trying backup URL: {current_url}")
            update_status_bar("proxy_test_backup_url")
for attempt in range(1, max_attempts + 1):
    if attempt > 1:
        logger.info(f"Proxy testi yeniden deneniyor (deneme {attempt}/{max_attempts})")
        update_status_bar("proxy_test_retrying", attempt=attempt, max_attempts=max_attempts)
        time.sleep(2)  # Yeniden denemeden önce 2 saniye bekle

    success, error_msg, status_code = _perform_proxy_test_single(proxy_address, current_url)


            if success:
                return True, get_text("proxy_test_success", url=current_url)

            # 503 hatası veya zaman aşımı varsa yeniden denemeye değer
            should_retry = (
                status_code == 503 or
                "timeout" in error_msg.lower() or
                "temporarily unavailable" in error_msg.lower()
            )
if not should_retry:
    # Geçici olmayan hatalar için yeniden deneme yapmayın, doğrudan bir sonraki URL'yi deneyin
    logger.info(f"{current_url} için yeniden deneme yapılamayan hata: {error_msg}")
    break


            if attempt == max_attempts:
                logger.warning(f"All {max_attempts} attempts failed for {current_url}: {error_msg}")

    # Tüm URL denemeleri ve yeniden girişimler başarısız oldu
    return False, get_text("proxy_test_all_failed")

def _proxy_test_thread(proxy_addr: str, test_url: str):
    """Proxy testini arka plandaki bir iş parçacığında yürütür"""
    try:
        success, message = _perform_proxy_test(proxy_addr, test_url)

        # GUI'yi ana iş parçacığında güncelle
        def update_gui():
            if success:
                messagebox.showinfo(get_text("info_title"), message, parent=root_widget)
                update_status_bar("proxy_test_success_status", url=test_url)
            else:
                messagebox.showerror(get_text("error_title"),
                                   get_text("proxy_test_failure", url=test_url, error=message),
                                   parent=root_widget)
                update_status_bar("proxy_test_failure_status", error=message)

        if root_widget:
            root_widget.after_idle(update_gui)

    except Exception as e:
        logger.error(f"Proxy test thread error: {e}", exc_info=True)
        def show_error():
            messagebox.showerror(get_text("error_title"),
                               f"Proxy testi sırasında hata oluştu: {e}",
                               parent=root_widget)
            update_status_bar("proxy_test_failure_status", error=str(e))

        if root_widget:
            root_widget.after_idle(show_error)

def test_proxy_connectivity_gui():
    if not proxy_enabled_var.get() or not proxy_address_var.get().strip():
        messagebox.showwarning(get_text("warning_title"), get_text("proxy_not_enabled_warn"), parent=root_widget)
        return

    proxy_addr_to_test = proxy_address_var.get().strip()
    test_url = LANG_TEXTS["proxy_test_url_default"] # Use the default from LANG_TEXTS

    # Testin başladığını göster
    update_status_bar("proxy_testing_status", proxy_addr=proxy_addr_to_test)
    # GUI'yi engellememek için arka planda bir iş parçacığında testi çalıştır
    test_thread = threading.Thread(
        target=_proxy_test_thread,
        args=(proxy_addr_to_test, test_url),
        daemon=True
    )
    test_thread.start()


def stop_selected_pid_from_list_gui():
    if not pid_listbox_widget: return
    selected_indices = pid_listbox_widget.curselection()
    if not selected_indices:
        messagebox.showwarning(get_text("warning_title"), get_text("pid_list_empty_for_stop_warn"), parent=root_widget)
        return
    selected_text = pid_listbox_widget.get(selected_indices[0]).strip()
    pid_to_stop = -1
    process_name_to_stop = get_text("unknown_process_name_placeholder")
    try:
        # Bilinen PID olmayan format olduğu için ilk olarak "işlem yok" girdisini kontrol edin
        no_process_indicator_zh = get_text("port_not_in_use_format", port_type="_", port_num="_").split("] ")[-1].strip()
        no_process_indicator_en = LANG_TEXTS["port_not_in_use_format"]["en"].split("] ")[-1].strip()
        general_no_pids_msg_zh = get_text("no_pids_found")
        general_no_pids_msg_en = LANG_TEXTS["no_pids_found"]["en"]

        is_no_process_entry = (no_process_indicator_zh in selected_text or \
                               no_process_indicator_en in selected_text or \
                               selected_text == general_no_pids_msg_zh or \
                               selected_text == general_no_pids_msg_en)
        if is_no_process_entry:
            logger.info(f"Selected item is a 'no process' entry: {selected_text}")
            return # Silently return for "no process" entries

        # Formatı ayrıştırmayı deneyin: "[Tür - Port] PID - Ad (Yol)" veya "PID - Ad (Yol)"
        # Bu regex, ayrıntılı formatı veya basit "PID - Ad" formatını eşleştirecektir
        # İsteğe bağlı "[...]" başlangıcını işlemek için yeterince esnektir
        match = re.match(r"^(?:\[[^\]]+\]\s*)?(\d+)\s*-\s*(.*)$", selected_text)
        if match:
            pid_to_stop = int(match.group(1))
            process_name_to_stop = match.group(2).strip()
        elif selected_text.isdigit(): # Handles if the listbox item is just a PID
            pid_to_stop = int(selected_text)
            # process_name_to_stop remains the default unknown
        else:
            # Genuine parsing error for an unexpected format
            messagebox.showerror(get_text("error_title"), get_text("error_parsing_pid", selection=selected_text), parent=root_widget)
            return
    except ValueError: # Catches int() conversion errors
        messagebox.showerror(get_text("error_title"), get_text("error_parsing_pid", selection=selected_text), parent=root_widget)
        return

    # Bu noktada pid_to_stop hâlâ -1 ise, işlenmeyen bir durum veya ayrıştırmada mantık hatası olduğu anlamına gelir.
    # Yukarıdaki dönüşler, hata veya "işlem yok" durumu varsa pid_to_stop == -1 olacak şekilde buraya ulaşmasını engellemelidir.
    if pid_to_stop == -1:
        # Bu yol, "işlem yok" mesajı olarak tanımlanmayan ve ValueError oluşturmamış ayrıştırılamayan bir dizeyi ima eder.
        logger.warning(f"PID ayrıştırması, 'işlem yok' olmayan giriş için -1 sonucunu verdi: {selected_text}. Bu beklenmeyen bir format veya mantık boşluğunu gösterir.")
        messagebox.showerror(get_text("error_title"), get_text("error_parsing_pid", selection=selected_text), parent=root_widget)
        return
    if messagebox.askyesno(get_text("confirm_stop_pid_title"), get_text("confirm_stop_pid_message", pid=pid_to_stop, name=process_name_to_stop), parent=root_widget):
        normal_kill_success = kill_process_pid(pid_to_stop)
        if normal_kill_success:
            messagebox.showinfo(get_text("info_title"), get_text("terminate_request_sent", pid=pid_to_stop, name=process_name_to_stop), parent=root_widget)
        else:
            # Normal izinlerle durdurma başarısız oldu, yönetici izniyle denensin mi sorusunu sorun
            if messagebox.askyesno(get_text("confirm_stop_pid_admin_title"),
                               get_text("confirm_stop_pid_admin_message", pid=pid_to_stop, name=process_name_to_stop),
                               parent=root_widget):
                admin_kill_success = kill_process_pid_admin(pid_to_stop)
                if admin_kill_success:
                    messagebox.showinfo(get_text("info_title"), get_text("admin_stop_success", pid=pid_to_stop), parent=root_widget)
                else:
                    messagebox.showwarning(get_text("warning_title"), get_text("admin_stop_failure", pid=pid_to_stop, error="bilinmeyen hata"), parent=root_widget)
            else:
                messagebox.showwarning(get_text("warning_title"), get_text("terminate_attempt_failed", pid=pid_to_stop, name=process_name_to_stop), parent=root_widget)
        query_port_and_display_pids_gui()
def kill_process_pid_admin(pid: int) -> bool:
    """Yönetici izinleriyle işlemi sonlandırmayı dener."""
    system = platform.system()
    success = False
    logger.info(f"PID: {pid} işlemini yönetici izinleriyle sonlandırmayı deniyor (Sistem: {system})")
    try:
        if system == "Windows":
            # Windows'ta PowerShell ile yönetici izinleriyle taskkill çalıştır
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin() == 0:
                # Şu anki kullanıcı yönetici değilse, yeni bir işlemi yönetici izinleriyle başlatmayı dene
                # PowerShell komutunu hazırla
                logger.info(f"Şu anda yönetici değil, PowerShell ile yetkilendirme yükseltmesi kullanılıyor")
                ps_cmd = f"Start-Process -Verb RunAs taskkill -ArgumentList '/PID {pid} /F /T'"
                logger.debug(f"PowerShell komutu yürütülüyor: {ps_cmd}")
                result = subprocess.run(["powershell", "-Command", ps_cmd],
                                     capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                logger.info(f"PowerShell komutu sonucu: Dönüş kodu={result.returncode}, Çıktı={result.stdout}, Hata={result.stderr}")
                success = result.returncode == 0
            else:
                # Zaten yöneticiyse, doğrudan taskkill çalıştır
                logger.info(f"Zaten yönetici izinlerinde, doğrudan taskkill çalıştırılıyor")
                result = subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                                     capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                logger.info(f"Taskkill komutu sonucu: Dönüş kodu={result.returncode}, Çıktı={result.stdout}, Hata={result.stderr}")
                success = result.returncode == 0
        elif system in ["Linux", "Darwin"]:  # Linux veya macOS
            # İşlemi sonlandırmak için sudo kullan
            logger.info(f"Yeni terminalde sudo kullanarak işlemi sonlandırıyor")
            cmd = ["sudo", "kill", "-9", str(pid)]
            # GUI programları için, terminalde kullanıcıdan şifre girmesini istediğimiz için yeni bir terminal penceresi kullan
            if system == "Darwin":  # macOS
                logger.info(f"macOS'ta AppleScript kullanarak Terminal açılıyor ve sudo komutu yürütülüyor")
                applescript = f'tell application "Terminal" to do script "sudo kill -9 {pid}"'
                result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)
                logger.info(f"AppleScript sonucu: Dönüş kodu={result.returncode}, Çıktı={result.stdout}, Hata={result.stderr}")
                success = result.returncode == 0
            else:  # Linux
                # Kullanılabilir terminal emülatörünü bul
                import shutil
                logger.info(f"Linux'ta kullanılabilir terminal emülatörleri aranıyor")
                terminal_emulator = shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal") or \
                                   shutil.which("konsole") or shutil.which("xfce4-terminal") or shutil.which("xterm")
                if terminal_emulator:
                    logger.info(f"Terminal emülatörü kullanılıyor: {terminal_emulator}")
                    if "gnome-terminal" in terminal_emulator:
                        logger.info(f"gnome-terminal için özel işlem")
                        result = subprocess.run([terminal_emulator, "--", "sudo", "kill", "-9", str(pid)])
                    else:
                        logger.info(f"Genel terminal başlatma komutu kullanılıyor")
                        result = subprocess.run([terminal_emulator, "-e", f"sudo kill -9 {pid}"])
                    logger.info(f"Terminal komutu sonucu: Dönüş kodu={result.returncode}")
                    success = result.returncode == 0
                else:
                    # Terminal emülatörü bulunamazsa, doğrudan sudo kullanmayı dene
                    logger.warning(f"Terminal emülatörü bulunamadı, doğrudan sudo kullanmayı dene (sudo iznine sahip olabilir)")
                    result = subprocess.run(["sudo", "kill", "-9", str(pid)], capture_output=True, text=True)
                    logger.info(f"Doğrudan sudo komutu sonucu: Dönüş kodu={result.returncode}, Çıktı={result.stdout}, Hata={result.stderr}")
                    success = result.returncode == 0
    except Exception as e:
        logger.error(f"PID {pid} işlemi yönetici izinleriyle sonlandırılırken hata oluştu: {e}", exc_info=True)
        success = False

    logger.info(f"PID: {pid} işlemini yönetici izinleriyle sonlandırma sonucu: {'Başarılı' if success else 'Başarısız'}")
    return success


def kill_custom_pid_gui():
    if not custom_pid_entry_var or not root_widget: return
    pid_str = custom_pid_entry_var.get()
    if not pid_str:
        messagebox.showwarning(get_text("warning_title"), get_text("pid_input_empty_warn"), parent=root_widget)
        return
    if not pid_str.isdigit():
        messagebox.showwarning(get_text("warning_title"), get_text("pid_input_invalid_warn"), parent=root_widget)
        return
    pid_to_kill = int(pid_str)
    process_name_to_kill = get_process_name_by_pid(pid_to_kill)
    confirm_msg = get_text("confirm_stop_pid_message", pid=pid_to_kill, name=process_name_to_kill)
    if messagebox.askyesno(get_text("confirm_kill_custom_pid_title"), confirm_msg, parent=root_widget):
        normal_kill_success = kill_process_pid(pid_to_kill)
        if normal_kill_success:
            messagebox.showinfo(get_text("info_title"), get_text("terminate_request_sent", pid=pid_to_kill, name=process_name_to_kill), parent=root_widget)
        else:
            # Normal izinlerle durdurma başarısız oldu, yönetici izinleriyle denensin mi sorusunu sor
            if messagebox.askyesno(get_text("confirm_stop_pid_admin_title"),
                                get_text("confirm_stop_pid_admin_message", pid=pid_to_kill, name=process_name_to_kill),
                                parent=root_widget):
                admin_kill_success = kill_process_pid_admin(pid_to_kill)
                if admin_kill_success:
                    messagebox.showinfo(get_text("info_title"), get_text("admin_stop_success", pid=pid_to_kill), parent=root_widget)
                else:
                    messagebox.showwarning(get_text("warning_title"), get_text("admin_stop_failure", pid=pid_to_kill, error="bilinmeyen hata"), parent=root_widget)
            else:
                messagebox.showwarning(get_text("warning_title"), get_text("terminate_attempt_failed", pid=pid_to_kill, name=process_name_to_kill), parent=root_widget)
        custom_pid_entry_var.set("")
        query_port_and_display_pids_gui()

menu_bar_ref: Optional[tk.Menu] = None

def update_all_ui_texts_gui():
    if not root_widget: return
    root_widget.title(get_text("title"))
    for item in widgets_to_translate:
        widget = item["widget"]
        key = item["key"]
        prop = item.get("property", "text")
        text_val = get_text(key, **item.get("kwargs", {}))
        if hasattr(widget, 'config'):
            try: widget.config(**{prop: text_val})
            except tk.TclError: pass
    current_status_text = process_status_text_var.get() if process_status_text_var else ""
    is_idle_status = any(current_status_text == LANG_TEXTS["status_idle"].get(lang_code, "") for lang_code in LANG_TEXTS["status_idle"])
    if is_idle_status: update_status_bar("status_idle")

def switch_language_gui(lang_code: str):
    global current_language
    if lang_code in LANG_TEXTS["title"]:
        current_language = lang_code
        update_all_ui_texts_gui()

def build_gui(root: tk.Tk):
    global process_status_text_var, port_entry_var, camoufox_debug_port_var, pid_listbox_widget, widgets_to_translate, managed_process_info, root_widget, menu_bar_ref, custom_pid_entry_var
    global stream_port_enabled_var, stream_port_var, helper_enabled_var, helper_endpoint_var, port_auto_check_var, proxy_address_var, proxy_enabled_var
    global active_auth_file_display_var # Yeni global değişken
    global pid_list_lbl_frame_ref # Global değişkenin burada ilan edildiğinden emin ol
    global g_config # Yeni global

    root_widget = root
    root.title(get_text("title"))
    root.minsize(950, 600)

    # Kaydedilen yapılandırmayı yükle
    g_config = load_config()

    s = ttk.Style()
    s.configure('TButton', padding=3)
    s.configure('TLabelFrame.Label', font=('Default', 10, 'bold'))
    s.configure('TLabelFrame', padding=4)
    try:
        os.makedirs(ACTIVE_AUTH_DIR, exist_ok=True)
        os.makedirs(SAVED_AUTH_DIR, exist_ok=True)
    except OSError as e:
        messagebox.showerror(get_text("error_title"), f"Kimlik doğrulama dizinleri oluşturulamadı: {e}")

    process_status_text_var = tk.StringVar(value=get_text("status_idle"))
    port_entry_var = tk.StringVar(value=str(g_config.get("fastapi_port", DEFAULT_FASTAPI_PORT)))
    camoufox_debug_port_var = tk.StringVar(value=str(g_config.get("camoufox_debug_port", DEFAULT_CAMOUFOX_PORT_GUI)))
    custom_pid_entry_var = tk.StringVar()
    stream_port_enabled_var = tk.BooleanVar(value=g_config.get("stream_port_enabled", True))
    stream_port_var = tk.StringVar(value=str(g_config.get("stream_port", "3120")))
    helper_enabled_var = tk.BooleanVar(value=g_config.get("helper_enabled", False))
    helper_endpoint_var = tk.StringVar(value=g_config.get("helper_endpoint", ""))
    port_auto_check_var = tk.BooleanVar(value=True)
    proxy_address_var = tk.StringVar(value=g_config.get("proxy_address", "http://127.0.0.1:7890"))
    proxy_enabled_var = tk.BooleanVar(value=g_config.get("proxy_enabled", False))
    active_auth_file_display_var = tk.StringVar() # Başlangıçta boş; _update_active_auth_display tarafından güncellenecek
    # Bağlantı mantığı: Proxy'yi zorla etkinleştirme yaklaşımı kaldırıldı, yapılandırma daha esnek
    # Kullanıcı akış proxy'sini ve tarayıcı proxy'sini ihtiyaçlarına göre ayrı ayrı ayarlayabilir
    def on_stream_proxy_toggle(*args):
        # Proxy'yi zorla etkinleştirmek yerine kullanıcıya seçim özgürlüğü bırak
        pass
    stream_port_enabled_var.trace_add("write", on_stream_proxy_toggle)



    menu_bar_ref = tk.Menu(root)
    lang_menu = tk.Menu(menu_bar_ref, tearoff=0)
    lang_menu.add_command(label="Çince (Chinese)", command=lambda: switch_language_gui('zh'))
    lang_menu.add_command(label="English", command=lambda: switch_language_gui('en'))
    menu_bar_ref.add_cascade(label="Language", menu=lang_menu)
    root.config(menu=menu_bar_ref)

    # --- Ana PanedWindow üç sütun düzenini uygular ---
    main_paned_window = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
    main_paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # --- Sol sütun çerçevesi ---
    left_frame_container = ttk.Frame(main_paned_window, padding="5")
    main_paned_window.add(left_frame_container, weight=3) # Sol sütunun başlangıç ağırlığını artır
    left_frame_container.columnconfigure(0, weight=1)
    # Satır ağırlıklarını ayarla; launch_options_frame ile auth_section arasında boşluk bırak veya sıkı tut
    # port_section, launch_options_frame ve auth_section sırasını varsayar
    left_frame_container.rowconfigure(0, weight=0) # port_section
    left_frame_container.rowconfigure(1, weight=0) # launch_options_frame
    left_frame_container.rowconfigure(2, weight=0) # auth_section taşındıktan sonra
    left_frame_container.rowconfigure(3, weight=1) # Kalan alanı doldurmak için yer tutucu çerçeve

    left_current_row = 0
    # Port yapılandırma bölümü
    port_section = ttk.LabelFrame(left_frame_container, text="")
    port_section.grid(row=left_current_row, column=0, sticky="ew", padx=2, pady=(2,10))
    widgets_to_translate.append({"widget": port_section, "key": "port_section_label", "property": "text"})
    left_current_row += 1

    # Sıfırlama ve hizmet kapatma rehberi düğmeleri ekle
    port_controls_frame = ttk.Frame(port_section)
    port_controls_frame.pack(fill=tk.X, padx=5, pady=3)
    btn_reset = ttk.Button(port_controls_frame, text="", command=reset_to_defaults)
    btn_reset.pack(side=tk.LEFT, padx=(0,5))
    widgets_to_translate.append({"widget": btn_reset, "key": "reset_button"})

    btn_closing_guide = ttk.Button(port_controls_frame, text="", command=show_service_closing_guide)
    btn_closing_guide.pack(side=tk.RIGHT, padx=(5,0))
    widgets_to_translate.append({"widget": btn_closing_guide, "key": "service_closing_guide_btn"})

    # Dahili kontroller port_section içinde kalır; pack ile sıkı yerleşim sağlar
    # FastAPI Port
    fastapi_frame = ttk.Frame(port_section)
    fastapi_frame.pack(fill=tk.X, padx=5, pady=3)
    lbl_port = ttk.Label(fastapi_frame, text="")
    lbl_port.pack(side=tk.LEFT, padx=(0,5))
    widgets_to_translate.append({"widget": lbl_port, "key": "fastapi_port_label"})
    entry_port = ttk.Entry(fastapi_frame, textvariable=port_entry_var, width=12)
    entry_port.pack(side=tk.LEFT, expand=True, fill=tk.X)
    # Camoufox Debug Port
    camoufox_frame = ttk.Frame(port_section)
    camoufox_frame.pack(fill=tk.X, padx=5, pady=3)
    lbl_camoufox_debug_port = ttk.Label(camoufox_frame, text="")
    lbl_camoufox_debug_port.pack(side=tk.LEFT, padx=(0,5))
    widgets_to_translate.append({"widget": lbl_camoufox_debug_port, "key": "camoufox_debug_port_label"})
    entry_camoufox_debug_port = ttk.Entry(camoufox_frame, textvariable=camoufox_debug_port_var, width=12)
    entry_camoufox_debug_port.pack(side=tk.LEFT, expand=True, fill=tk.X)
    # Stream Proxy Port
    stream_port_frame_outer = ttk.Frame(port_section)
    stream_port_frame_outer.pack(fill=tk.X, padx=5, pady=3)
    stream_port_checkbox = ttk.Checkbutton(stream_port_frame_outer, variable=stream_port_enabled_var, text="")
    stream_port_checkbox.pack(side=tk.LEFT, padx=(0,2))
    widgets_to_translate.append({"widget": stream_port_checkbox, "key": "enable_stream_proxy_label", "property": "text"})
    stream_port_details_frame = ttk.Frame(stream_port_frame_outer)
    stream_port_details_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
    lbl_stream_port = ttk.Label(stream_port_details_frame, text="")
    lbl_stream_port.pack(side=tk.LEFT, padx=(0,5))
    widgets_to_translate.append({"widget": lbl_stream_port, "key": "stream_proxy_port_label"})
    entry_stream_port = ttk.Entry(stream_port_details_frame, textvariable=stream_port_var, width=10)
    entry_stream_port.pack(side=tk.LEFT, expand=True, fill=tk.X)
    # Helper Service
    helper_frame_outer = ttk.Frame(port_section)
    helper_frame_outer.pack(fill=tk.X, padx=5, pady=3)
    helper_checkbox = ttk.Checkbutton(helper_frame_outer, variable=helper_enabled_var, text="")
    helper_checkbox.pack(side=tk.LEFT, padx=(0,2))
    widgets_to_translate.append({"widget": helper_checkbox, "key": "enable_helper_label", "property": "text"})
    helper_details_frame = ttk.Frame(helper_frame_outer)
    helper_details_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
    lbl_helper_endpoint = ttk.Label(helper_details_frame, text="")
    lbl_helper_endpoint.pack(side=tk.LEFT, padx=(0,5))
    widgets_to_translate.append({"widget": lbl_helper_endpoint, "key": "helper_endpoint_label"})
    entry_helper_endpoint = ttk.Entry(helper_details_frame, textvariable=helper_endpoint_var)
    entry_helper_endpoint.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Ayırıcı ekle
    ttk.Separator(port_section, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=(8,5))

    # Proxy yapılandırma bölümü - bağımsız LabelFrame
    proxy_section = ttk.LabelFrame(port_section, text="")
    proxy_section.pack(fill=tk.X, padx=5, pady=(5,8))
    widgets_to_translate.append({"widget": proxy_section, "key": "proxy_section_label", "property": "text"})

    # Proxy etkinleştirme seçim kutusu
    proxy_enable_frame = ttk.Frame(proxy_section)
    proxy_enable_frame.pack(fill=tk.X, padx=5, pady=(5,3))
    proxy_checkbox = ttk.Checkbutton(proxy_enable_frame, variable=proxy_enabled_var, text="")
    proxy_checkbox.pack(side=tk.LEFT)
    widgets_to_translate.append({"widget": proxy_checkbox, "key": "enable_proxy_label", "property": "text"})

    # Proxy adresi girişi
    proxy_address_frame = ttk.Frame(proxy_section)
    proxy_address_frame.pack(fill=tk.X, padx=5, pady=(0,5))
    lbl_proxy_address = ttk.Label(proxy_address_frame, text="")
    lbl_proxy_address.pack(side=tk.LEFT, padx=(0,5))
    widgets_to_translate.append({"widget": lbl_proxy_address, "key": "proxy_address_label"})
    entry_proxy_address = ttk.Entry(proxy_address_frame, textvariable=proxy_address_var)
    entry_proxy_address.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,5))

    # Proxy testi düğmesi
    btn_test_proxy_inline = ttk.Button(proxy_address_frame, text="", command=test_proxy_connectivity_gui, width=8)
    btn_test_proxy_inline.pack(side=tk.RIGHT)
    widgets_to_translate.append({"widget": btn_test_proxy_inline, "key": "test_proxy_btn"})

    # Port auto check
    port_auto_check_frame = ttk.Frame(port_section)
    port_auto_check_frame.pack(fill=tk.X, padx=5, pady=3)
    port_auto_check_btn = ttk.Checkbutton(port_auto_check_frame, variable=port_auto_check_var, text="")
    port_auto_check_btn.pack(side=tk.LEFT)
    widgets_to_translate.append({"widget": port_auto_check_btn, "key": "port_auto_check", "property": "text"})

    # Başlatma seçenekleri bölümü
    launch_options_frame = ttk.LabelFrame(left_frame_container, text="")
    launch_options_frame.grid(row=left_current_row, column=0, sticky="ew", padx=2, pady=5)
    widgets_to_translate.append({"widget": launch_options_frame, "key": "launch_options_label", "property": "text"})
    left_current_row += 1
    lbl_launch_options_note = ttk.Label(launch_options_frame, text="", wraplength=240) # wraplength değerini ayarla
    lbl_launch_options_note.pack(fill=tk.X, padx=5, pady=(5, 8))
    widgets_to_translate.append({"widget": lbl_launch_options_note, "key": "launch_options_note_revised"})
    # Başlatma düğmeleri
    btn_headed = ttk.Button(launch_options_frame, text="", command=start_headed_interactive_gui)
    btn_headed.pack(fill=tk.X, padx=5, pady=3)
    widgets_to_translate.append({"widget": btn_headed, "key": "launch_headed_interactive_btn"})
    btn_headless = ttk.Button(launch_options_frame, text="", command=start_headless_gui) # command ve anahtar güncellendi
    btn_headless.pack(fill=tk.X, padx=5, pady=3)
    widgets_to_translate.append({"widget": btn_headless, "key": "launch_headless_btn"}) # Anahtar güncellendi
    btn_virtual_display = ttk.Button(launch_options_frame, text="", command=start_virtual_display_gui)
    btn_virtual_display.pack(fill=tk.X, padx=5, pady=3)
    widgets_to_translate.append({"widget": btn_virtual_display, "key": "launch_virtual_display_btn"})
    if platform.system() != "Linux":
        btn_virtual_display.state(['disabled'])

    # Separator for LLM service buttons
    ttk.Separator(launch_options_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=(8,5))

    # LLM Service Buttons
    btn_start_llm_service = ttk.Button(launch_options_frame, text="", command=start_llm_service_gui)
    btn_start_llm_service.pack(fill=tk.X, padx=5, pady=3)
    widgets_to_translate.append({"widget": btn_start_llm_service, "key": "launch_llm_service_btn"})

    btn_stop_llm_service = ttk.Button(launch_options_frame, text="", command=stop_llm_service_gui)
    btn_stop_llm_service.pack(fill=tk.X, padx=5, pady=3)
    widgets_to_translate.append({"widget": btn_stop_llm_service, "key": "stop_llm_service_btn"})

    # Artık gerekli olmayan "GUI tarafından yönetilen hizmeti durdur" düğmesini kaldır
    # btn_stop_service = ttk.Button(launch_options_frame, text="", command=stop_managed_service_gui)
    # btn_stop_service.pack(fill=tk.X, padx=5, pady=3)
    # widgets_to_translate.append({"widget": btn_stop_service, "key": "stop_gui_service_btn"})


# Sol taraftaki içeriği yukarıda tutmak için bir yer tutucu Frame ekleyin (alt boşlukları azaltır)
spacer_frame_left = ttk.Frame(left_frame_container)
spacer_frame_left.grid(row=left_current_row, column=0, sticky="nsew")
left_frame_container.rowconfigure(left_current_row, weight=1) # Yer tutucunun genişlemesini sağla


    # --- Orta sütun çerçevesi ---
    middle_frame_container = ttk.Frame(main_paned_window, padding="5")
    main_paned_window.add(middle_frame_container, weight=2) # Orta sütunun başlangıç ağırlığını ayarla
    middle_frame_container.columnconfigure(0, weight=1)
    middle_frame_container.rowconfigure(0, weight=1)
    middle_frame_container.rowconfigure(1, weight=0)
    middle_frame_container.rowconfigure(2, weight=0) # Kimlik doğrulama yönetimi artık orta sütunda

    middle_current_row = 0
    pid_section_frame = ttk.Frame(middle_frame_container)
    pid_section_frame.grid(row=middle_current_row, column=0, sticky="nsew", padx=2, pady=2)
    pid_section_frame.columnconfigure(0, weight=1)
    pid_section_frame.rowconfigure(0, weight=1)
    middle_current_row +=1

    global pid_list_lbl_frame_ref
    pid_list_lbl_frame_ref = ttk.LabelFrame(pid_section_frame, text=get_text("static_pid_list_title")) # Sabit başlığı kullan
    pid_list_lbl_frame_ref.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)
    pid_list_lbl_frame_ref.columnconfigure(0, weight=1)
    pid_list_lbl_frame_ref.rowconfigure(0, weight=1)
    pid_listbox_widget = tk.Listbox(pid_list_lbl_frame_ref, height=4, exportselection=False)
    pid_listbox_widget.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
    scrollbar = ttk.Scrollbar(pid_list_lbl_frame_ref, orient="vertical", command=pid_listbox_widget.yview)
    scrollbar.grid(row=0, column=1, sticky="ns", padx=(0,5), pady=5)
    pid_listbox_widget.config(yscrollcommand=scrollbar.set)

    pid_buttons_frame = ttk.Frame(pid_section_frame)
    pid_buttons_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5,2))
    pid_buttons_frame.columnconfigure(0, weight=1)
    pid_buttons_frame.columnconfigure(1, weight=1)
    btn_query = ttk.Button(pid_buttons_frame, text="", command=query_port_and_display_pids_gui)
    btn_query.grid(row=0, column=0, sticky="ew", padx=(0,2))
    widgets_to_translate.append({"widget": btn_query, "key": "query_pids_btn"})
    btn_stop_pid = ttk.Button(pid_buttons_frame, text="", command=stop_selected_pid_from_list_gui)
    btn_stop_pid.grid(row=0, column=1, sticky="ew", padx=(2,0))
    widgets_to_translate.append({"widget": btn_stop_pid, "key": "stop_selected_pid_btn"})

    # Proxy test butonu artık proxy yapılandırma bölümünde, burada tekrar etmiyor

    kill_custom_frame = ttk.LabelFrame(middle_frame_container, text="")
    kill_custom_frame.grid(row=middle_current_row, column=0, sticky="ew", padx=2, pady=5)
    widgets_to_translate.append({"widget": kill_custom_frame, "key": "kill_custom_pid_label", "property":"text"})
    middle_current_row += 1
    kill_custom_frame.columnconfigure(0, weight=1)
    entry_custom_pid = ttk.Entry(kill_custom_frame, textvariable=custom_pid_entry_var, width=10)
    entry_custom_pid.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
    btn_kill_custom_pid = ttk.Button(kill_custom_frame, text="", command=kill_custom_pid_gui)
    btn_kill_custom_pid.pack(side=tk.LEFT, padx=5, pady=5)
    widgets_to_translate.append({"widget": btn_kill_custom_pid, "key": "kill_custom_pid_btn"})

    if ENABLE_QWEN_LOGIN_SUPPORT:
        # Kimlik doğrulama dosyası yönetimi (orta sütuna PID sonlandırma işlevinin altına taşındı)
        auth_section_middle = ttk.LabelFrame(middle_frame_container, text="")
        auth_section_middle.grid(row=middle_current_row, column=0, sticky="ew", padx=2, pady=5)
        widgets_to_translate.append({"widget": auth_section_middle, "key": "auth_files_management", "property": "text"})
        middle_current_row += 1
        btn_manage_auth_middle = ttk.Button(auth_section_middle, text="", command=manage_auth_files_gui)
        btn_manage_auth_middle.pack(fill=tk.X, padx=5, pady=5)
        widgets_to_translate.append({"widget": btn_manage_auth_middle, "key": "manage_auth_files_btn"})

        # Mevcut kimlik doğrulama dosyasını göster
        auth_display_frame = ttk.Frame(auth_section_middle)
        auth_display_frame.pack(fill=tk.X, padx=5, pady=(0,5))
        lbl_current_auth_static = ttk.Label(auth_display_frame, text="")
        lbl_current_auth_static.pack(side=tk.LEFT)
        widgets_to_translate.append({"widget": lbl_current_auth_static, "key": "current_auth_file_display_label"})
        lbl_current_auth_dynamic = ttk.Label(auth_display_frame, textvariable=active_auth_file_display_var, wraplength=180)
        lbl_current_auth_dynamic.pack(side=tk.LEFT, fill=tk.X, expand=True)
    else:
        active_auth_file_display_var.set(get_text("current_auth_file_none"))

    # --- Sağ sütun çerçevesi ---
    right_frame_container = ttk.Frame(main_paned_window, padding="5")
    main_paned_window.add(right_frame_container, weight=2) # Sağ sütunun başlangıç ağırlığını ayarla, biraz daha küçük tut
    right_frame_container.columnconfigure(0, weight=1)
    right_frame_container.rowconfigure(1, weight=1)
    right_current_row = 0
    status_area_frame = ttk.LabelFrame(right_frame_container, text="")
    status_area_frame.grid(row=right_current_row, column=0, padx=2, pady=2, sticky="ew")
    widgets_to_translate.append({"widget": status_area_frame, "key": "status_label", "property": "text"})
    right_current_row += 1
    lbl_status_val = ttk.Label(status_area_frame, textvariable=process_status_text_var, wraplength=280)
    lbl_status_val.pack(fill=tk.X, padx=5, pady=5)
    def rewrap_status_label(event=None):
        if root_widget and lbl_status_val.winfo_exists():
            new_width = status_area_frame.winfo_width() - 20
            if new_width > 100: lbl_status_val.config(wraplength=new_width)
    status_area_frame.bind("<Configure>", rewrap_status_label)

    output_log_area_frame = ttk.LabelFrame(right_frame_container, text="")
    output_log_area_frame.grid(row=right_current_row, column=0, padx=2, pady=2, sticky="nsew")
    widgets_to_translate.append({"widget": output_log_area_frame, "key": "output_label", "property": "text"})
    output_log_area_frame.columnconfigure(0, weight=1)
    output_log_area_frame.rowconfigure(0, weight=1)
    output_scrolled_text = scrolledtext.ScrolledText(output_log_area_frame, height=10, width=35, wrap=tk.WORD, state=tk.DISABLED) # Genişliği ayarla
    output_scrolled_text.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
    managed_process_info["output_area"] = output_scrolled_text

    update_all_ui_texts_gui()
    query_port_and_display_pids_gui() # Başlangıçta FastAPI portunu sorgula
    _update_active_auth_display() # Başlangıçta kimlik doğrulama dosyasını güncelle
    root.protocol("WM_DELETE_WINDOW", on_app_close_main)

pid_list_lbl_frame_ref: Optional[ttk.LabelFrame] = None

# Başlatma parametrelerini toplamak ve doğrulamak için yardımcı fonksiyon eklendi
def _get_launch_parameters() -> Optional[Dict[str, Any]]:
    """GUI'den başlatma parametrelerini toplar ve doğrular. Geçersizse None döndürür."""
    params = {}
    try:
        params["fastapi_port"] = get_fastapi_port_from_gui()
        params["camoufox_debug_port"] = get_camoufox_debug_port_from_gui()

        params["stream_port_enabled"] = stream_port_enabled_var.get()
        sp_val_str = stream_port_var.get().strip()
        if params["stream_port_enabled"]:
            params["stream_port"] = int(sp_val_str) if sp_val_str else 3120
            if not (params["stream_port"] == 0 or 1024 <= params["stream_port"] <= 65535):
                messagebox.showwarning(get_text("warning_title"), get_text("stream_port_out_of_range"))
                return None
        else:
            params["stream_port"] = 0 # Etkin değilse port 0 kabul edilir (devre dışı)

        params["helper_enabled"] = helper_enabled_var.get()
        params["helper_endpoint"] = helper_endpoint_var.get().strip() if params["helper_enabled"] else ""

        return params
    except ValueError: # Genellikle int() dönüşümünden kaynaklanır
        messagebox.showwarning(get_text("warning_title"), get_text("enter_valid_port_warn")) # veya daha spesifik hata
        return None
    except Exception as e:
        messagebox.showerror(get_text("error_title"), f"Başlatma parametreleri alınırken hata oluştu: {e}")
        return None

# on_app_close_main fonksiyonunu hizmet bağımsızlığını yansıtacak şekilde güncelle
def on_app_close_main():
    # Mevcut yapılandırmayı kaydet
    save_config()

    # Attempt to stop LLM service if it's running
    if is_llm_service_running():
        logger.info("LLM service is running. Attempting to stop it before exiting GUI.")
        # We can call stop_llm_service_gui directly, but it shows a confirmation.
        # For closing, we might want a more direct stop or a specific "closing" stop.
        # For now, let's try a direct stop without user confirmation for this specific path.
        popen = llm_service_process_info.get("popen")
        service_name = get_text(llm_service_process_info.get("service_name_key", "llm_service_name_key"))
        if popen:
            try:
                logger.info(f"Sending SIGINT to {service_name} (PID: {popen.pid}) during app close.")
                if platform.system() == "Windows":
                    popen.terminate() # TerminateProcess on Windows
                else:
                    popen.send_signal(signal.SIGINT)

                # Give it a very short time to exit, don't block GUI closing for too long
                popen.wait(timeout=1.5)
                logger.info(f"{service_name} (PID: {popen.pid}) hopefully stopped during app close.")
            except subprocess.TimeoutExpired:
                logger.warning(f"{service_name} (PID: {popen.pid}) did not stop quickly during app close. May need manual cleanup.")
                popen.kill() # Force kill if it didn't stop
            except Exception as e:
                logger.error(f"Error stopping {service_name} during app close: {e}")
            finally:
                llm_service_process_info["popen"] = None # Clear it
# Hizmetler tümü bağımsız terminalde başlatılır, bu yüzden sadece kullanıcının GUI'yi kapatmak isteyip istemediğini onaylayın
if messagebox.askyesno(get_text("confirm_quit_title"), get_text("confirm_quit_message"), parent=root_widget):
    if root_widget:
        root_widget.destroy()


def show_service_closing_guide():
    messagebox.showinfo(
        get_text("service_closing_guide"),
        get_text("service_closing_guide_message"),
        parent=root_widget
    )

if __name__ == "__main__":
    if not os.path.exists(LAUNCH_CAMOUFOX_PY) or not os.path.exists(os.path.join(SCRIPT_DIR, SERVER_PY_FILENAME)):
        err_lang = current_language
        err_title_key = "startup_error_title"
        err_msg_key = "startup_script_not_found_msgbox"
        err_title = LANG_TEXTS[err_title_key].get(err_lang, LANG_TEXTS[err_title_key]['en'])
        err_msg_template = LANG_TEXTS[err_msg_key].get(err_lang, LANG_TEXTS[err_msg_key]['en'])
        err_msg = err_msg_template.format(script=f"{os.path.basename(LAUNCH_CAMOUFOX_PY)} or {SERVER_PY_FILENAME}")
        try:
            root_err = tk.Tk(); root_err.withdraw()
            messagebox.showerror(err_title, err_msg, parent=None)
            root_err.destroy()
        except tk.TclError:
            print(f"ERROR: {err_msg}", file=sys.stderr)
        sys.exit(1)
    app_root = tk.Tk()
    build_gui(app_root)
    app_root.mainloop()
