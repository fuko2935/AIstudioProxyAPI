# Docker Dağıtım Rehberi (AI Studio Proxy API)

> 📁 **Not**: Tüm Docker ile ilgili dosyalar `docker/` klasöründe tutulur; proje kökü bu sayede temiz kalır.

Bu rehber, AI Studio Proxy API uygulamasını Docker ile paketlemek ve işletmek için gereken adımları anlatır. İçerik; Poetry tabanlı bağımlılık yönetimi, `.env` dosyası ile yapılandırma, script enjeksiyonu ve günlük kullanım senaryolarını kapsar.

## 🐳 Genel Bakış

Docker dağıtımı şu avantajları sunar:
- ✅ **Ortam izolasyonu** – Konteyner sayesinde yerel bağımlılık çatışmaları ortadan kalkar.
- ✅ **Poetry ile yönetim** – Modern Python bağımlılık yönetimi konteyner içinde de korunur.
- ✅ **Merkezi yapılandırma** – `.env` dosyası ile tüm ayarlar tek noktadan yapılır.
- ✅ **Kolay güncelleme** – `bash update.sh` çalıştırmak yeterlidir.
- ✅ **Çoklu mimari desteği** – x86_64 ve ARM64 (Apple Silicon) sistemlerinde çalışır.
- ✅ **Kalıcı veri** – Kimlik doğrulama dosyaları ve loglar volume olarak saklanır.
- ✅ **Çok aşamalı derleme** – Daha küçük imaj ve hızlı build süreleri.

## Gerekli Ön Koşullar

- **Docker**: Docker Desktop (Windows/macOS) veya Docker Engine (Linux) kurulmuş ve çalışır durumda olmalı. İndir: [docker.com/get-started](https://www.docker.com/get-started)
- **Proje kaynak kodu**: Depoyu yerel makinenize klonlayın.
- **Kimlik doğrulama dosyaları**: İlk kurulumda kimlik doğrulama işlemini ana makinede tamamlayın; konteyner bu dosyaları kullanır.

## 🔧 Docker Ortamı Özellikleri

- **Temel imaj**: `python:3.10-slim-bookworm`
- **Python sürümü**: 3.10 (konteyner içinde sabittir, ana makinenizden bağımsızdır)
- **Bağımlılık yöneticisi**: Poetry
- **Derleme modeli**: Builder + runtime aşamaları
- **Desteklenen mimariler**: x86_64 ve ARM64
- **Modüler tasarım**: Projenin modüler yapısı konteynerde eksiksiz desteklenir
- **Sanal ortam**: Poetry konteyner içinde sanal ortam kurulumunu otomatik yönetir

## 1. Docker Dosyalarını Tanıyın

`docker/` klasörünün içinde şu önemli dosyalar bulunur:

- **`Dockerfile`** – İmajın nasıl oluşturulacağını belirler.
- **`.dockerignore`** – Derleme sırasında konteynere gönderilmeyecek dosya/dizinleri listeler.
- **`docker-compose.yml`** – Compose ile çok adımlı orkestrasyon sağlar.
- **`supervisord.conf`** – Varsa, birden fazla sürecin aynı konteyner içinde yönetilmesini tanımlar.

## 2. Docker İmajı Oluşturma

Terminali proje kökünde açıp aşağıdaki yollardan birini izleyin:

```bash
# Yöntem 1: docker compose (önerilen)
cd docker
docker compose build

# Yöntem 2: docker build (proje kökünde)
docker build -f docker/Dockerfile -t ai-studio-proxy:latest .
```

Komut açıklamaları:
- `docker build`: İmaj oluşturur.
- `-t ai-studio-proxy:latest`: İmaj adı ve etiketi (tag) tanımlar.
- `.`: Derleme bağlamının mevcut dizin olduğunu belirtir.

Build tamamlandığında `docker images` ile `ai-studio-proxy:latest` imajını görebilirsiniz.

## 3. Konteyneri Çalıştırma

### Yöntem A – Docker Compose (önerilen)

```bash
# 1. Yapılandırma dosyasını hazırla
cd docker
cp .env.docker .env
# .env dosyasını ihtiyaçlarınıza göre düzenleyin

# 2. Hizmeti başlat
docker compose up -d

# 3. Günlükleri izle
docker compose logs -f

# 4. Hizmeti durdur
docker compose down
```

### Yöntem B – `docker run` komutu

**.env dosyasıyla çalıştırma (önerilen):**
```bash
docker run -d \
    -p <ana_makine_servis_portu>:2048 \
    -p <ana_makine_stream_portu>:3120 \
    -v "$(pwd)/../auth_profiles":/app/auth_profiles \
    -v "$(pwd)/.env":/app/.env \
    # Opsiyonel: kendi sertifikalarınızı kullanmak için aşağıdaki satırı aktif edin
    # -v "$(pwd)/../certs":/app/certs \
    --name ai-studio-proxy-container \
    ai-studio-proxy:latest
```

**Ortam değişkenleriyle çalıştırma:**
```bash
docker run -d \
    -p <ana_makine_servis_portu>:2048 \
    -p <ana_makine_stream_portu>:3120 \
    -v "$(pwd)/../auth_profiles":/app/auth_profiles \
    # -v "$(pwd)/../certs":/app/certs \
    -e PORT=8000 \
    -e DEFAULT_FASTAPI_PORT=2048 \
    -e DEFAULT_CAMOUFOX_PORT=9222 \
    -e STREAM_PORT=3120 \
    -e SERVER_LOG_LEVEL=INFO \
    -e DEBUG_LOGS_ENABLED=false \
    -e AUTO_CONFIRM_LOGIN=true \
    # Gerekirse proxy ayarlarını açın
    # -e HTTP_PROXY="http://adres:port" \
    # -e HTTPS_PROXY="http://adres:port" \
    # -e UNIFIED_PROXY_CONFIG="http://adres:port" \
    --name ai-studio-proxy-container \
    ai-studio-proxy:latest
```

Komutlardaki yer tutucuları (`<ana_makine_servis_portu>` vb.) gerçek değerlerle değiştirin. `auth_profiles/` ve opsiyonel `certs/` dizinlerinin ana makinede mevcut olduğundan emin olun.

## İlk Çalıştırma Öncesi Hazırlık

1. **`.env` dosyasını oluşturun**
   ```bash
   cd docker
   cp .env.docker .env
   nano .env
   ```
   `.env` kullanmanın faydaları:
   - Yapılandırmalar tek dosyada toplanır.
   - `git pull` sonrası ayarlar kaybolmaz.
   - Docker konteyneri dosyayı otomatik okur.
   - `.gitignore` sayesinde gizli kalır.
2. **`auth_profiles/` dizinini hazırlayın** – Kimlik doğrulama dosyalarınızı bu dizine ekleyin.
3. **(Opsiyonel) `certs/` dizini** – Özel TLS sertifikaları kullanacaksanız burada saklayın.

## 4. Yapılandırma Ayrıntıları

### `.env` dosyasını konteynere bağlamak
```bash
-v "$(pwd)/.env":/app/.env
```

### Sık kullanılan ayarlar
```env
PORT=8000
DEFAULT_FASTAPI_PORT=2048
DEFAULT_CAMOUFOX_PORT=9222
STREAM_PORT=3120

HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
UNIFIED_PROXY_CONFIG=http://127.0.0.1:7890

SERVER_LOG_LEVEL=INFO
DEBUG_LOGS_ENABLED=false
TRACE_LOGS_ENABLED=false

AUTO_CONFIRM_LOGIN=true
AUTO_SAVE_AUTH=false
AUTH_SAVE_TIMEOUT=30

ENABLE_SCRIPT_INJECTION=true
USERSCRIPT_PATH=browser_utils/more_modles.js

DEFAULT_TEMPERATURE=1.0
DEFAULT_MAX_OUTPUT_TOKENS=65536
DEFAULT_TOP_P=0.95
```

### Öncelik sırası
1. `docker run` ile verilen `-e` ortam değişkenleri
2. Konteynerde `/app/.env` olarak mount edilen `.env` dosyası
3. `Dockerfile` içindeki `ENV` tanımları

### Örnek tam komut
```bash
docker run -d \
    -p 8080:2048 \
    -p 8081:3120 \
    -v "$(pwd)/../auth_profiles":/app/auth_profiles \
    -v "$(pwd)/.env":/app/.env \
    --name ai-studio-proxy-container \
    ai-studio-proxy:latest
```

## 5. Konteyner Yönetimi

- Çalışan konteynerleri listele: `docker ps`
- Logları izle: `docker logs -f ai-studio-proxy-container`
- Konteyneri durdur: `docker stop ai-studio-proxy-container`
- Durdurulmuş konteyneri başlat: `docker start ai-studio-proxy-container`
- Yeniden başlat: `docker restart ai-studio-proxy-container`
- Kabuk aç: `docker exec -it ai-studio-proxy-container /bin/bash`
- Sil: `docker stop ai-studio-proxy-container && docker rm ai-studio-proxy-container`

## 6. Güncelleme Akışı

1. Eski konteyneri durdurup silin.
2. Yeni kodları alın (`git pull`).
3. İmajı yeniden oluşturun (`docker compose build` veya `docker build ...`).
4. Konteyneri yeniden başlatın (aynı `docker compose up -d` veya `docker run` komutu).

## 7. Temizlik

- Belirli bir imajı sil: `docker rmi ai-studio-proxy:latest`
- Kullanılmayan kaynakları temizle: `docker system prune` (tüm imajlar için `-a` ekleyin; dikkatli olun)

## Script Enjeksiyonu (v3.0) 🆕

Docker ortamı, script enjeksiyonunu tam destekler:
- **Playwright tabanlı ağ engelleme** ile çapraz doğrulama
- **İkili güvence** – ağ engelleme + userscript enjeksiyonu
- **Model listesi** Tampermonkey betiğinden otomatik ayrıştırılır
- **Tek veri kaynağı** – Ön uç ve arka uç aynı listeyi kullanır
- **Bakım kolaylığı** – Betik güncellendiğinde yapılandırma gerekmez

`.env` ayarları:
```env
ENABLE_SCRIPT_INJECTION=true
USERSCRIPT_PATH=browser_utils/more_modles.js
```

Kendi betiğinizi kullanmak isterseniz `browser_utils/my_script.js` dosyası oluşturup `docker-compose.yml` içinde ilgili volume satırını aktif hale getirin veya `.env` içinde `USERSCRIPT_PATH` değerini değiştirin.

## Dikkat Edilecekler

1. **Kimlik doğrulama** – `auth_profiles/active/` altındaki dosyalar konteyner için erişilebilir olmalı.
2. **Portlar** – Varsayılan 2048 ve 3120 portlarının ana makinede boş olduğundan emin olun.
3. **Log takibi** – Sorun giderme sırasında `docker logs` komutu çok faydalıdır.
4. **Script enjeksiyonu** – Gerekirse `ENABLE_SCRIPT_INJECTION=false` yaparak kapatabilirsiniz.

## Yapılandırma Özeti ⭐

- `.env` dosyası her ortam için özelleştirilebilir.
- `.env.docker` şablonunu ihtiyaçlarınıza göre çoğaltın (örn. `.env.prod`).
- Güncelleme rutini: `git pull` → `bash update.sh` → `docker compose up -d`.
- Log ve kimlik doğrulama dosyaları host üzerinde kalır; veri kaybı yaşamazsınız.

Bu rehberle Docker üzerinde AI Studio Proxy API kurulumunuzu zahmetsizce yönetebilirsiniz. Sorularınız için proje dokümantasyonuna veya issue bölümüne başvurabilirsiniz.
