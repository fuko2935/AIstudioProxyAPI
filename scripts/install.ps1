# AI Studio Proxy API Tek Tık Kurulum Scripti (Windows PowerShell)
# Modern Bağımlılık Yönetimi için Poetry Kullanımı

# Hata işleme ayarla
$ErrorActionPreference = "Stop"

# Renk Fonksiyonları
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Log-Info {
    param([string]$Message)
    Write-ColorOutput "[INFO] $Message" "Blue"
}

function Log-Success {
    param([string]$Message)
    Write-ColorOutput "[SUCCESS] $Message" "Green"
}

function Log-Warning {
    param([string]$Message)
    Write-ColorOutput "[WARNING] $Message" "Yellow"
}

function Log-Error {
    param([string]$Message)
    Write-ColorOutput "[ERROR] $Message" "Red"
}

# Komutun var olup olmadığını kontrol et
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# Python sürümünü kontrol et
function Test-Python {
    Log-Info "Python sürümünü kontrol et..."
    
    $pythonCmd = $null
    if (Test-Command "python") {
        $pythonCmd = "python"
    }
    elseif (Test-Command "py") {
        $pythonCmd = "py"
    }
    else {
        Log-Error "Python bulunamadı. Lütfen önce Python 3.9+ yükleyin."
        exit 1
    }
    
    try {
        $pythonVersion = & $pythonCmd --version 2>&1
        $versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
        
        if ($versionMatch) {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]
            
            if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
                Log-Error "Python sürümü çok düşük: $pythonVersion. Python 3.9+ gerekli."
                exit 1
            }
            
            Log-Success "Python sürümü: $pythonVersion ✓"
            return $pythonCmd
        }
        else {
            Log-Error "Python sürümü çözümlenemiyor"
            exit 1
        }
    }
    catch {
        Log-Error "Python sürüm kontrolü başarısız: $_"
        exit 1
    }
}

# Poetry'yi Yükle
function Install-Poetry {
    if (Test-Command "poetry") {
        Log-Success "Poetry yüklü ✓"
        return
    }
    
    Log-Info "Poetry yükleniyor..."
    try {
        (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
        
        # Çevre değişkenlerini yenile
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
        
        if (Test-Command "poetry") {
            Log-Success "Poetry yükleme başarılı ✓"
        }
        else {
            Log-Error "Poetry yükleme başarısız. Lütfen Poetry'yi manuel olarak yükleyin."
            exit 1
        }
    }
    catch {
        Log-Error "Poetry yükleme başarısız: $_"
        exit 1
    }
}

# Projeyi Klonla
function Clone-Project {
    Log-Info "Proje klonlanıyor..."
    
    if (Test-Path "AIstudioProxyAPI") {
        Log-Warning "Proje dizini mevcut, klonlama atlandı"
        Set-Location "AIstudioProxyAPI"
    }
    else {
        try {
            git clone https://github.com/CJackHwang/AIstudioProxyAPI.git
            Set-Location "AIstudioProxyAPI"
            Log-Success "Proje klonlama başarılı ✓"
        }
        catch {
            Log-Error "Proje klonlama başarısız: $_"
            exit 1
        }
    }
}

# Bağımlılıkları Yükle
function Install-Dependencies {
    Log-Info "Proje bağımlılıkları yükleniyor..."
    try {
        poetry install
        Log-Success "Bağımlılık yükleme başarılı ✓"
    }
    catch {
        Log-Error "Bağımlılık yükleme başarısız: $_"
        exit 1
    }
}

# Camoufox'u İndir
function Download-Camoufox {
    Log-Info "Camoufox tarayıcısı indiriliyor..."
    try {
        poetry run camoufox fetch
        Log-Success "Camoufox indirme başarılı ✓"
    }
    catch {
        Log-Warning "Camoufox indirme başarısız, ancak ana işlevleri etkilemiyor: $_"
    }
}

# Playwright Bağımlılıklarını Yükle
function Install-PlaywrightDeps {
    Log-Info "Playwright bağımlılıkları yükleniyor..."
    try {
        poetry run playwright install-deps firefox
    }
    catch {
        Log-Warning "Playwright bağımlılık yükleme başarısız, ancak ana işlevleri etkilemiyor"
    }
}

# Yapılandırma Dosyası Oluştur
function Create-Config {
    Log-Info "Yapılandırma dosyası oluşturuluyor..."
    
    if (!(Test-Path ".env") -and (Test-Path ".env.example")) {
        Copy-Item ".env.example" ".env"
        Log-Success "Yapılandırma dosyası oluşturma başarılı ✓"
        Log-Info "Kişisel yapılandırma için .env dosyasını düzenleyin"
    }
    else {
        Log-Warning "Yapılandırma dosyası mevcut veya şablon yok"
    }
}

# Kurulumu Doğrula
function Test-Installation {
    Log-Info "Kurulum doğrulanıyor..."
    
    try {
        # Poetry ortamını kontrol et
        poetry env info | Out-Null

        # Kritik bağımlılıkları kontrol et
        poetry run python -c "import fastapi, playwright, camoufox"
        
        Log-Success "Kurulum doğrulaması başarılı ✓"
    }
    catch {
        Log-Error "Kurulum doğrulaması başarısız: $_"
        exit 1
    }
}

# Sonraki Adımları Göster
function Show-NextSteps {
    Write-Host ""
    Log-Success "🎉 Kurulum tamamlandı!"
    Write-Host ""
    Write-Host "Sonraki adımlar:"
    Write-Host "1. Proje dizinine gir: cd AIstudioProxyAPI"
    Write-Host "2. Sanal ortamı etkinleştir: poetry env activate"
    Write-Host "3. Çevre değişkenlerini yapılandır: notepad .env"
    Write-Host "4. İlk kimlik doğrulama ayarı: poetry run python launch_camoufox.py --debug"
    Write-Host "5. Günlük çalışma: poetry run python launch_camoufox.py --headless"
    Write-Host ""
    Write-Host "Detaylı dokümantasyon:"
    Write-Host "- Çevre yapılandırması: docs/environment-configuration.md"
    Write-Host "- Kimlik doğrulama ayarı: docs/authentication-setup.md"
    Write-Host "- Günlük kullanım: docs/daily-usage.md"
    Write-Host ""
}

# Ana fonksiyon
function Main {
    Write-Host "🚀 AI Studio Proxy API Tek Tık Kurulum Scripti"
    Write-Host "Modern Bağımlılık Yönetimi için Poetry Kullanımı"
    Write-Host ""

    $pythonCmd = Test-Python
    Install-Poetry
    Clone-Project
    Install-Dependencies
    Download-Camoufox
    Install-PlaywrightDeps
    Create-Config
    Test-Installation
    Show-NextSteps
}

# Ana fonksiyonu çalıştır
try {
    Main
}
catch {
    Log-Error "Kurulum sırasında hata oluştu: $_"
    exit 1
}
