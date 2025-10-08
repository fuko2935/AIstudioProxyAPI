#!/bin/bash

# AI Studio Proxy API Tek Tık Kurulum Scripti (macOS/Linux)
# Bağımlılık yönetimi için Poetry kullan

set -e

# Renk Tanımları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Günlük Fonksiyonları
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Komutun var olup olmadığını kontrol et
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Python Sürümünü Kontrol Et
check_python() {
    log_info "Python sürümü kontrol ediliyor..."
    
    if command_exists python3; then
        PYTHON_CMD="python3"
    elif command_exists python; then
        PYTHON_CMD="python"
    else
        log_error "Python bulunamadı. Lütfen önce Python 3.9+ yükleyin."
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
        log_error "Python sürümü çok düşük: $PYTHON_VERSION. Python 3.9+ gerekli."
        exit 1
    fi
    
    log_success "Python sürümü: $PYTHON_VERSION ✓"
}

# Poetry'yi Yükle
install_poetry() {
    if command_exists poetry; then
        log_success "Poetry yüklü ✓"
        return
    fi
    
    log_info "Poetry yükleniyor..."
    curl -sSL https://install.python-poetry.org | $PYTHON_CMD -
    
    # Poetry'yi PATH'e ekle
    export PATH="$HOME/.local/bin:$PATH"
    
    if command_exists poetry; then
        log_success "Poetry yükleme başarılı ✓"
    else
        log_error "Poetry yükleme başarısız. Lütfen Poetry'yi manuel olarak yükleyin."
        exit 1
    fi
}

# Projeyi klonla
clone_project() {
    log_info "Projeyi klonla..."
    
    if [ -d "AIstudioProxyAPI" ]; then
        log_warning "Proje dizini mevcut, klonlama atlandı"
        cd AIstudioProxyAPI
    else
        git clone https://github.com/CJackHwang/AIstudioProxyAPI.git
        cd AIstudioProxyAPI
        log_success "Proje klonlama başarılı ✓"
    fi
}

# Proje bağımlılıklarını yükle
install_dependencies() {
    log_info "Proje bağımlılıklarını yükle..."
    poetry install
    log_success "Bağımlılık yükleme başarılı ✓"
}

# Camoufox tarayıcısını indir
download_camoufox() {
    log_info "Camoufox tarayıcısını indir..."
    poetry run camoufox fetch
    log_success "Camoufox indirme başarılı ✓"
}

# Playwright bağımlılıklarını yükle
install_playwright_deps() {
    log_info "Playwright bağımlılıklarını yükle..."
    poetry run playwright install-deps firefox || {
        log_warning "Playwright bağımlılıkları yüklenemedi, ama ana fonksiyonları etkilemez"
    }
}

# Yapılandırma dosyası oluştur
create_config() {
    log_info "Yapılandırma dosyası oluştur..."
    
    if [ ! -f ".env" ] && [ -f ".env.example" ]; then
        cp .env.example .env
        log_success "Yapılandırma dosyası oluşturma başarılı ✓"
        log_info "Kişisel yapılandırma için .env dosyasını düzenleyin"
    else
        log_warning "Yapılandırma dosyası mevcut veya şablon yok"
    fi
}

# Kurulumu doğrula
verify_installation() {
    log_info "Kurulumu doğrula..."
    
    # Poetry ortamını kontrol et
    poetry env info >/dev/null 2>&1 || {
        log_error "Poetry ortam doğrulaması başarısız"
        exit 1
    }
    
    # Kritik bağımlılıkları kontrol et
    poetry run python -c "import fastapi, playwright, camoufox" || {
        log_error "Kritik bağımlılık doğrulaması başarısız"
        exit 1
    }
    
    log_success "Kurulum doğrulaması başarılı ✓"
}

# Sonraki adımları göster
show_next_steps() {
    echo
    log_success "🎉 Kurulum tamamlandı!"
    echo
    echo "Sonraki adımlar:"
    echo "1. Proje dizinine gir: cd AIstudioProxyAPI"
    echo "2. Sanal ortamı etkinleştir: poetry env activate"
    echo "3. Çevre değişkenlerini yapılandır: nano .env"
    echo "4. İlk kimlik doğrulama ayarı: python launch_camoufox.py --debug"
    echo "5. Günlük çalışma: python launch_camoufox.py --headless"
    echo
    echo "Detaylı dokümantasyon:"
    echo "- Çevre yapılandırması: docs/environment-configuration.md"
    echo "- Kimlik doğrulama ayarı: docs/authentication-setup.md"
    echo "- Günlük kullanım: docs/daily-usage.md"
    echo
}

# Ana fonksiyon
main() {
    echo "🚀 AI Studio Proxy API Tek Tık Kurulum Scripti"
    echo "Modern bağımlılık yönetimi için Poetry kullan"
    echo

    check_python
    install_poetry
    clone_project
    install_dependencies
    download_camoufox
    install_playwright_deps
    create_config
    verify_installation
    show_next_steps
}

# Ana fonksiyonu çalıştır
main "$@"
