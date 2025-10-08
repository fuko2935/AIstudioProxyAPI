# Kurulum Kılavuzu

Bu belge, Poetry tabanlı ayrıntılı kurulum adımlarını ve ortam yapılandırma talimatlarını sağlar.

## 🔧 Sistem Gereksinimleri

### Temel Gereksinimler

- **Python**: 3.9+ (Önerilen 3.10+ veya 3.11+)
  - **Önerilen Sürüm**: En iyi performans ve uyumluluk için Python 3.11+
  - **Minimum Gereksinim**: Python 3.9 (tüm mevcut bağımlılık sürümlerini destekler)
  - **Tam Destek**: Python 3.9, 3.10, 3.11, 3.12, 3.13
- **Poetry**: 1.4+ (Modern Python bağımlılık yönetim aracı)
- **Git**: Depoyu klonlamak için (önerilir)
- **Google AI Studio Hesabı**: Normal şekilde erişilebilir ve kullanılabilir olmalı
- **Node.js**: 16+ (İsteğe bağlı, Pyright tür denetimi için)

### Sistem Bağımlılıkları

- **Linux**: `xvfb` (sanal ekran, isteğe bağlı)
  - Debian/Ubuntu: `sudo apt-get update && sudo apt-get install -y xvfb`
  - Fedora: `sudo dnf install -y xorg-x11-server-Xvfb`
- **macOS**: Genellikle ek bağımlılık gerekmez
- **Windows**: Genellikle ek bağımlılık gerekmez

## 🚀 Hızlı Kurulum (Önerilen)

### Tek Tıkla Kurulum Betiği

```bash
# macOS/Linux kullanıcıları
curl -sSL https://raw.githubusercontent.com/CJackHwang/AIstudioProxyAPI/main/scripts/install.sh | bash

# Windows kullanıcıları (PowerShell)
iwr -useb https://raw.githubusercontent.com/CJackHwang/AIstudioProxyAPI/main/scripts/install.ps1 | iex
```

## 📋 Manuel Kurulum Adımları

### 1. Poetry Kurulumu

Eğer Poetry kurulu değilse, lütfen önce kurun:

```bash
# macOS/Linux
curl -sSL https://install.python-poetry.org | python3 -

# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# Veya paket yöneticisi kullanın
# macOS: brew install poetry
# Ubuntu/Debian: apt install python3-poetry
# Windows: winget install Python.Poetry
```

### 2. Depoyu Klonlama

```bash
git clone https://github.com/CJackHwang/AIstudioProxyAPI.git
cd AIstudioProxyAPI
```

### 3. Bağımlılıkları Kurma

Poetry otomatik olarak bir sanal ortam oluşturacak ve tüm bağımlılıkları kuracaktır:

```bash
# Üretim bağımlılıklarını kur
poetry install

# Geliştirme bağımlılıkları dahil kur (geliştiriciler için önerilir)
poetry install --with dev
```

**Poetry Avantajları**:

- ✅ Sanal ortamları otomatik olarak oluşturur ve yönetir
- ✅ Bağımlılık çözümleme ve sürüm kilitleme (`poetry.lock`)
- ✅ Üretim ve geliştirme bağımlılıklarını ayırır
- ✅ Anlamsal sürüm kontrolü

### 4. Sanal Ortamı Aktifleştirme

```bash
# Poetry tarafından oluşturulan sanal ortamı aktifleştir
poetry env activate

# Veya her komutun başına poetry run ekleyin
poetry run python --version
```

### 5. Camoufox Tarayıcısını İndirme

```bash
# Poetry ortamında Camoufox tarayıcısını indir
poetry run camoufox fetch

# Veya aktifleştirilmiş ortamda
camoufox fetch
```

**Bağımlılık Sürüm Notları** (Poetry tarafından yönetilir):

- **FastAPI 0.115.12**: Performans optimizasyonları ve yeni özellikler içeren en son kararlı sürüm
  - Yeni Query/Header/Cookie parametre modeli desteği
  - Geliştirilmiş tür ipuçları ve doğrulama mekanizması
  - Daha iyi OpenAPI belge oluşturma ve asenkron performans
- **Pydantic >=2.7.1,<3.0.0**: Modern veri doğrulama kütüphanesi, sürüm aralığı uyumluluğu sağlar
- **Uvicorn 0.29.0**: Asenkron işleme ve HTTP/2 desteği sunan yüksek performanslı ASGI sunucusu
- **Playwright**: Tarayıcı otomasyonu, sayfa etkileşimi ve ağ kesintisi için en son sürüm
- **Camoufox 0.4.11**: Coğrafi IP verileri ve artırılmış gizlilik içeren parmak izi önleyici tarayıcı
- **WebSockets 12.0**: Gerçek zamanlı günlük aktarımı, durum izleme ve Web UI iletişimi için
- **aiohttp ~3.9.5**: Proxy ve akış desteği sunan asenkron HTTP istemcisi
- **python-dotenv 1.0.1**: .env dosyası yapılandırmasını destekleyen ortam değişkeni yönetimi

### 6. Playwright Tarayıcı Bağımlılıklarını Kurma (İsteğe Bağlı)

Camoufox kendi Firefox'unu kullansa da, ilk çalıştırmada bazı temel bağımlılıkların kurulması gerekebilir:

```bash
# Poetry ortamında Playwright bağımlılıklarını kur
poetry run playwright install-deps firefox

# Veya aktifleştirilmiş ortamda
playwright install-deps firefox
```

Eğer `camoufox fetch` ağ sorunları nedeniyle başarısız olursa, projedeki [`fetch_camoufox_data.py`](../fetch_camoufox_data.py) betiğini çalıştırmayı deneyebilirsiniz (ayrıntılar için [Sorun Giderme Kılavuzu](troubleshooting.md)).

## 🔍 Kurulumu Doğrulama

### Poetry Ortamını Kontrol Etme

```bash
# Poetry ortam bilgilerini görüntüle
poetry env info

# Kurulu bağımlılıkları görüntüle
poetry show

# Bağımlılık ağacını görüntüle
poetry show --tree

# Python sürümünü kontrol et
poetry run python --version
```

### Kritik Bileşenleri Kontrol Etme

```bash
# Camoufox'u kontrol et
poetry run camoufox --version

# FastAPI'yi kontrol et
poetry run python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"

# Playwright'ı kontrol et
poetry run python -c "import playwright; print('Playwright: OK')"
```

## 🚀 Servis Nasıl Başlatılır

Kurulumu ve ortam yapılandırmasını tamamladıktan sonra, `.env.example` dosyasını `.env` olarak kopyalamanız ve ihtiyaçlarınıza göre düzenlemeniz şiddetle tavsiye edilir. Bu, sonraki başlatma komutlarını büyük ölçüde basitleştirecektir.

```bash
# Yapılandırma şablonunu kopyala
cp .env.example .env

# Yapılandırma dosyasını düzenle
nano .env  # veya başka bir düzenleyici kullanın
```

Yapılandırmayı tamamladıktan sonra, servisi başlatmak için aşağıdaki yöntemlerden birini seçebilirsiniz:

### 1. GUI ile Başlatma (En Çok Önerilen)

Çoğu kullanıcı, özellikle yeni başlayanlar için grafik arayüz (GUI) başlatıcısını kullanmanızı şiddetle tavsiye ederiz. Bu en basit ve en sezgisel yoldur.

```bash
# Poetry ortamında çalıştır
poetry run python gui_launcher.py

# Veya sanal ortamı zaten aktifleştirdiyseniz
python gui_launcher.py
```

GUI başlatıcısı, arka plan işlemlerini otomatik olarak yönetir ve servisi başlatıp durdurmak ve günlükleri görüntülemek için basit bir arayüz sağlar.

### 2. Komut Satırından Başlatma (İleri Düzey)

Komut satırına aşina olan kullanıcılar, servisi başlatmak için doğrudan `launch_camoufox.py` betiğini kullanabilirler.

```bash
# Başsız (headless) modu başlat, bu sunucu dağıtımları için yaygın bir yöntemdir
poetry run python launch_camoufox.py --headless

# Hata ayıklama (debug) modunu başlat, tarayıcı arayüzünü gösterir
poetry run python launch_camoufox.py --debug
```

Başlatma davranışını kontrol etmek için farklı parametreler ekleyebilirsiniz, örneğin:
- `--headless`: Tarayıcıyı arka planda çalıştırır, arayüz göstermez.
- `--debug`: Başlatıldığında tarayıcı arayüzünü gösterir, hata ayıklamayı kolaylaştırır.
- Daha fazla parametre için [Gelişmiş Yapılandırma Kılavuzu](advanced-configuration.md)'na bakın.

### 3. Docker ile Başlatma

Docker'a aşina iseniz, servisi dağıtmak için konteynerleştirilmiş bir yöntem de kullanabilirsiniz. Bu yöntem daha iyi ortam yalıtımı sağlayabilir.

Ayrıntılı Docker başlatma kılavuzu için lütfen şuraya bakın:
- **[Docker Dağıtım Kılavuzu](../docker/README-Docker.md)**

## Çoklu Platform Kılavuzu

### macOS / Linux

- Kurulum süreci genellikle sorunsuzdur. Python ve pip'in doğru şekilde kurulduğundan ve sistem PATH'inde yapılandırıldığından emin olun.
- Sanal ortamı etkinleştirmek için `source venv/bin/activate` kullanın.
- `playwright install-deps firefox`, bazı bağımlılık kitaplıklarını kurmak için sistem paket yöneticisi (Debian/Ubuntu için `apt`, Fedora/CentOS için `yum`/`dnf`, macOS için `brew` gibi) gerektirebilir. Komut başarısız olursa, lütfen hata çıktısını dikkatlice okuyun ve eksik sistem paketlerini istemlere göre kurun. Bazen `playwright install-deps` komutunu çalıştırmak için `sudo` ayrıcalıkları gerekebilir.
- Güvenlik duvarı genellikle yerel erişimi engellemez, ancak başka bir makineden erişiyorsanız, bağlantı noktasının (varsayılan 2048) açık olduğundan emin olmanız gerekir.
- Linux kullanıcıları için, `--virtual-display` bayrağıyla başlatmayı düşünebilirsiniz (`xvfb`'nin önceden kurulması gerekir). Bu, tarayıcıyı çalıştırmak için bir sanal ekran ortamı oluşturmak üzere Xvfb'yi kullanır, bu da tespit edilme riskini daha da azaltmaya ve web sayfasının normal konuşmasını sağlamaya yardımcı olabilir.

### Windows

#### Yerel Windows

- Python'u kurarken "Add Python to PATH" seçeneğini işaretlediğinizden emin olun.
- Sanal ortamı etkinleştirmek için `venv\\Scripts\\activate` kullanın.
- Windows Güvenlik Duvarı, Uvicorn/FastAPI'nin bağlantı noktasını dinlemesini engelleyebilir. Bağlantı sorunları yaşarsanız (özellikle diğer cihazlardan erişirken), Windows Güvenlik Duvarı ayarlarını kontrol edin ve Python veya belirli bağlantı noktası için gelen bağlantılara izin verin.
- `playwright install-deps` komutunun yerel Windows'ta sınırlı bir etkisi vardır (esas olarak Linux için kullanılır), ancak `camoufox fetch` komutunu çalıştırmak (dahili olarak Playwright'ı çağırır) doğru tarayıcının indirilmesini sağlar.
- **[`gui_launcher.py`](../gui_launcher.py) ile başlatmanız önerilir**, arka plan işlemlerini ve kullanıcı etkileşimini otomatik olarak yönetirler. [`launch_camoufox.py`](../launch_camoufox.py) dosyasını doğrudan çalıştırırsanız, terminal penceresinin açık kalması gerekir.

#### WSL (Windows Subsystem for Linux)

- **Önerilen**: Linux ortamına alışkın kullanıcılar için WSL (özellikle WSL2) daha iyi bir deneyim sunar.
- WSL ortamında, kurulum ve bağımlılık yönetimi için **macOS / Linux** adımlarını izleyin (genellikle `apt` komutu kullanılır).
- Ağ erişimine dikkat etmek gerekir:
  - Windows'tan WSL'de çalışan bir servise erişim: Genellikle `localhost` veya WSL tarafından atanan IP adresi üzerinden erişilebilir.
  - Yerel ağdaki diğer cihazlardan WSL'de çalışan bir servise erişim: Windows Güvenlik Duvarı'nı ve WSL'nin ağ ayarlarını yapılandırmanız gerekebilir (WSL2'nin ağına genellikle dışarıdan erişmek daha kolaydır).
- Tüm komutlar (`git clone`, `pip install`, `camoufox fetch`, `python launch_camoufox.py` vb.) WSL terminali içinde çalıştırılmalıdır.
- WSL'de `--debug` modunu çalıştırmak: [`launch_camoufox.py --debug`](../launch_camoufox.py) Camoufox'u başlatmayı deneyecektir. WSL'niz GUI uygulama desteğiyle (WSLg veya üçüncü taraf bir X Sunucusu gibi) yapılandırılmışsa, tarayıcı arayüzünü görebilirsiniz. Aksi takdirde, arayüzü görüntüleyemeyebilir, ancak hizmetin kendisi yine de başlatılmaya çalışacaktır. Başsız mod ( [`gui_launcher.py`](../gui_launcher.py) aracılığıyla başlatılır) etkilenmez.

## Ortam Değişkenlerini Yapılandırma (Önerilen)

Kurulumdan sonra, sonraki kullanımı basitleştirmek için `.env` dosyasını yapılandırmanız şiddetle tavsiye edilir:

### Yapılandırma Dosyası Oluşturma

```bash
# Yapılandırma şablonunu kopyala
cp .env.example .env

# Yapılandırma dosyasını düzenle
nano .env  # veya başka bir düzenleyici kullanın
```

### Temel Yapılandırma Örneği

```env
# Hizmet bağlantı noktası yapılandırması
DEFAULT_FASTAPI_PORT=2048
STREAM_PORT=3120

# Proxy yapılandırması (gerekirse)
# HTTP_PROXY=http://127.0.0.1:7890

# Günlük yapılandırması
SERVER_LOG_LEVEL=INFO
DEBUG_LOGS_ENABLED=false
```

Yapılandırma tamamlandıktan sonra, başlatma komutları çok basit hale gelecektir:

```bash
# Karmaşık parametreler olmadan basit başlatma
python launch_camoufox.py --headless
```

Ayrıntılı yapılandırma talimatları için [Ortam Değişkeni Yapılandırma Kılavuzu](environment-configuration.md)'na bakın.

## İsteğe Bağlı: API Anahtarlarını Yapılandırma

Hizmetinizi korumak için API anahtarlarını da yapılandırabilirsiniz:

### Anahtar Dosyası Oluşturma

`auth_profiles` dizininde `key.txt` dosyasını oluşturun (eğer yoksa):

```bash
# Dizin ve anahtar dosyası oluştur
mkdir -p auth_profiles && touch auth_profiles/key.txt

# Anahtar ekle (her satıra bir tane)
echo "ilk-api-anahtarınız" >> key.txt
echo "ikinci-api-anahtarınız" >> key.txt
```

### Anahtar Biçimi Gereksinimleri

- Her satıra bir anahtar
- En az 8 karakter
- Boş satırları ve yorum satırlarını destekler (`#` ile başlayanlar)
- UTF-8 kodlaması kullanın

### Örnek Anahtar Dosyası

```
# API anahtarı yapılandırma dosyası
# Her satıra bir anahtar

sk-1234567890abcdef
my-secure-api-key-2024
admin-key-for-testing

# Bu bir yorum satırıdır, göz ardı edilecektir
```

### Güvenlik Notları

- **Anahtar dosyası yok**: Hizmet kimlik doğrulaması gerektirmez, herkes API'ye erişebilir
- **Anahtar dosyası var**: Tüm API istekleri geçerli bir anahtar sağlamalıdır
- **Anahtar koruması**: Lütfen anahtar dosyasını güvende tutun ve sürüm kontrol sistemine göndermeyin

## Sonraki Adımlar

Kurulum tamamlandıktan sonra, lütfen şunlara bakın:

- **[Ortam Değişkeni Yapılandırma Kılavuzu](environment-configuration.md)** - ⭐ Önce yapılandırmanız önerilir, sonraki kullanımı basitleştirir
- [İlk Çalıştırma ve Kimlik Doğrulama Kılavuzu](authentication-setup.md)
- [Günlük Kullanım Kılavuzu](daily-usage.md)
- [API Kullanım Kılavuzu](api-usage.md) - Ayrıntılı anahtar yönetimi talimatlarını içerir
- [Sorun Giderme Kılavuzu](troubleshooting.md)