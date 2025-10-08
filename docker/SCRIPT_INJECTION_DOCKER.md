# Docker Ortamı Betik Enjeksiyonu Yapılandırma Rehberi

## Genel Bakış

Bu rehber, Docker ortamında Tampermonkey betik enjeksiyonu özelliğini yapılandırmak için hazırlanmıştır.

## Hızlı Başlangıç

### 1. Temel yapılandırma

```bash
# docker dizinine gir
cd docker

# yapılandırma şablonunu kopyala
cp .env.docker .env

# yapılandırma dosyasını düzenle
nano .env
```

`.env` dosyasında aşağıdaki ayarların bulunduğundan emin olun:

```env
# betik enjeksiyonunu etkinleştir
ENABLE_SCRIPT_INJECTION=true

# varsayılan betiği kullan (model verileri doğrudan betikten okunur)
USERSCRIPT_PATH=browser_utils/more_modles.js
```

### 2. Konteyneri başlat

```bash
# oluştur ve başlat
docker compose up -d

# betik enjeksiyonu durumunu günlüklerden doğrula
docker compose logs -f | grep "Script injection"
```

## Özelleştirme

### Yöntem 1: Betik dosyasını doğrudan değiştir

```bash
# 1. Özel Tampermonkey betiğini oluştur
cp ../browser_utils/more_modles.js ../browser_utils/my_custom_script.js

# 2. Betikteki MODELS_TO_INJECT dizisini düzenle
nano ../browser_utils/my_custom_script.js

# 3. Konteyneri yeniden başlat
docker compose restart
```

### Yöntem 2: Özel betiği bağla

```bash
# 1. Özel betik dosyasını oluştur
cp ../browser_utils/more_modles.js ../browser_utils/my_script.js

# 2. docker-compose.yml dosyasında aşağıdaki satırları etkinleştir ve düzenle:
# volumes:
#   - ../browser_utils/my_script.js:/app/browser_utils/more_modles.js:ro

# 3. Hizmeti yeniden başlat
docker compose down
docker compose up -d
```

### Yöntem 3: Ortam değişkeni ile yapılandır

```bash
# 1. .env dosyasında yolu güncelle
echo "USERSCRIPT_PATH=browser_utils/my_custom_script.js" >> .env

# 2. Karşılık gelen betik dosyasını oluştur
cp ../browser_utils/more_modles.js ../browser_utils/my_custom_script.js

# 3. Konteyneri yeniden başlat
docker compose restart
```

## Betik Enjeksiyonunu Doğrulama

### Günlükleri kontrol et

```bash
# betik enjeksiyonu ile ilgili günlükleri görüntüle
docker compose logs | grep -E "(Script injection|script.*inject|Model enhancement)"

# günlükleri anlık izle
docker compose logs -f | grep -E "(Script injection|script.*inject|Model enhancement)"
```

### Beklenen günlük çıktısı

Başarılı bir betik enjeksiyonu aşağıdakine benzer günlükler üretir:

```
Ağ engelleme ve betik enjeksiyonu ayarlanıyor...
Model listesi için ağ engelleme başarıyla yapılandırıldı
Tampermonkey betiğinden 6 model ayrıştırıldı
API model listesine 6 enjeksiyon modeli eklendi
✅ Betik enjeksiyonu başarılı, modeller Tampermonkey betiği ile birebir aynı görünüyor
   Ayrıştırılan modeller: 👑 Kingfall, ✨ Gemini 2.5 Pro, 🦁 Goldmane...
```

### Konteyner içinde kontrol et

```bash
# konteynere gir
docker compose exec ai-studio-proxy /bin/bash

# betik dosyasını incele
cat /app/browser_utils/more_modles.js

# betik dosyası listesini kontrol et
ls -la /app/browser_utils/*.js

# konteynerden çık
exit
```

## Sorun Giderme

### Betik enjeksiyonu başarısızse

1. **Yapılandırma dosyası yolunu kontrol et**:
   ```bash
   docker compose exec ai-studio-proxy ls -la /app/browser_utils/
   ```

2. **Dosya izinlerini kontrol et**:
   ```bash
   docker compose exec ai-studio-proxy cat /app/browser_utils/more_modles.js
   ```

3. **Ayrıntılı hata günlüklerini incele**:
   ```bash
   docker compose logs | grep -A 5 -B 5 "Script injection"
   ```

### Betik dosyası geçersizse

1. **JavaScript biçimini doğrula**:
   ```bash
   # JavaScript söz dizimini ana makinede doğrula
   node -c browser_utils/more_modles.js
   ```

2. **Gerekli alanları kontrol et**:
   Her modelin `name` ve `displayName` alanlarına sahip olduğundan emin olun.

### Betik enjeksiyonunu devre dışı bırakma

Sorun yaşarsanız geçici olarak devre dışı bırakabilirsiniz:

```bash
# .env dosyasında ayarla
echo "ENABLE_SCRIPT_INJECTION=false" >> .env

# konteyneri yeniden başlat
docker compose restart
```

## Gelişmiş Yapılandırma

### Özel betik kullanma

```bash
# 1. Özel betiği browser_utils/ dizinine yerleştir
cp your_custom_script.js ../browser_utils/custom_injector.js

# 2. .env dosyasında betik yolunu güncelle
echo "USERSCRIPT_PATH=browser_utils/custom_injector.js" >> .env

# 3. Konteyneri yeniden başlat
docker compose restart
```

### Çoklu ortam yapılandırması

```bash
# geliştirme ortamı
cp .env.docker .env.dev
# .env.dev dosyasını düzenle

# üretim ortamı
cp .env.docker .env.prod
# .env.prod dosyasını düzenle

# belirli bir ortamla başlat
cp .env.prod .env
docker compose up -d
```

## Dikkat Edilecekler

1. **Dosya bağlama**: Ana makinedeki dosya yollarının doğru olduğundan emin olun.
2. **İzin sorunları**: Docker konteynerindeki dosya izinlerinin güncellenmesi gerekebilir.
3. **Yeniden başlatma zorunluluğu**: Yapılandırma değişiklikleri sonrasında konteyneri yeniden başlatın.
4. **Günlük izleme**: Betik enjeksiyonunun durumunu günlüklerden takip edin.
5. **Yedekleme**: Çalışan yapılandırma dosyalarını yedeklemeniz önerilir.

## Örnek yapılandırma dosyası

Tam yapılandırma biçimi ve seçenekleri için `model_configs_docker_example.json` dosyasına bakabilirsiniz.
