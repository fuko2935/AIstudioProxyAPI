# Docker Dağıtım Dosyaları

Bu dizin AI Studio Proxy API projesi için tüm Docker ilgili dosyaları içerir.

## 📁 Dosya Açıklamaları

- **`Dockerfile`** - Docker imajının oluşturulma adımlarını tanımlar
- **`docker-compose.yml`** - Docker Compose yapılandırması
- **`.env.docker`** - Docker ortamı için örnek `.env` dosyası
- **`README-Docker.md`** - Ayrıntılı Docker dağıtım rehberi

## 🚀 Hızlı Başlangıç

### 1. Yapılandırma dosyasını hazırla

```bash
# docker dizinine gir
cp .env.docker .env
nano .env  # yapılandırmayı düzenle
```

### 2. Hizmeti başlat

```bash
# docker dizinine gir
cd docker

# hizmeti oluştur ve başlat
docker compose up -d

# günlükleri izle
docker compose logs -f
```

### 3. Sürüm güncellemesi

```bash
# docker dizininde çalıştır
bash update.sh
```

## 📖 Ayrıntılı Doküman

Tam Docker dağıtım rehberi için bkz. [README-Docker.md](README-Docker.md)

## 🔧 Sık Kullanılan Komutlar

```bash
# hizmet durumunu görüntüle
docker compose ps

# günlükleri izle
docker compose logs -f

# hizmeti durdur
docker compose down

# hizmeti yeniden başlat
docker compose restart

# konteynere bağlan
docker compose exec ai-studio-proxy /bin/bash
```

## 🌟 Öne Çıkan Avantajlar

- ✅ **Tek noktadan yapılandırma**: Tüm ayarlar `.env` dosyasıyla yönetilir
- ✅ **Sorunsuz güncelleme**: `bash update.sh` ile kolayca güncelleyebilirsiniz
- ✅ **Ortam izolasyonu**: Konteyner kullanımı ortam çakışmalarını önler
- ✅ **Kalıcı yapılandırma**: Kimlik doğrulama dosyaları ve günlükler kalıcı olarak saklanır

## ⚠️ Dikkat Edilecekler

1. **Kimlik doğrulama dosyası**: İlk çalıştırmada ana makinede kimlik doğrulama dosyasını oluşturmalısınız
2. **Port ayarları**: Ana makinedeki portların meşgul olmadığından emin olun
3. **Yapılandırma dosyası**: `.env` dosyası `docker/` dizininde bulunmalıdır ki ortam değişkenleri doğru yüklensin
4. **Dizin düzeni**: Docker dosyaları `docker/` klasörüne taşındı; proje kökü daha düzenli kalır
