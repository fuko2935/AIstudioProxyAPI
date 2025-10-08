# API Kullanım Kılavuzu

Bu kılavuz, AI Studio Proxy API'nin çeşitli özelliklerinin ve uç noktalarının nasıl kullanılacağını ayrıntılı olarak açıklar.

## Sunucu Yapılandırması

Proxy sunucusu varsayılan olarak `http://127.0.0.1:2048` adresinde dinleme yapar. Bağlantı noktası aşağıdaki yollarla yapılandırılabilir:

- **Ortam Değişkenleri**: `.env` dosyasında `PORT=2048` veya `DEFAULT_FASTAPI_PORT=2048` ayarlayın
- **Komut Satırı Argümanları**: `--server-port` argümanını kullanın
- **GUI Başlatıcı**: Grafik arayüzde bağlantı noktasını doğrudan yapılandırın

Yapılandırma yönetimi için `.env` dosyasını kullanmanız önerilir, ayrıntılar için [Ortam Değişkeni Yapılandırma Kılavuzu](environment-configuration.md) bölümüne bakın.

## API Anahtarı Yapılandırması

### key.txt Dosya Yapılandırması

Proje, API anahtarlarını yönetmek için `auth_profiles/key.txt` dosyasını kullanır:

**Dosya Konumu**: Proje kök dizinindeki `key.txt` dosyası

**Dosya Biçimi**: Her satırda bir API anahtarı, boş satırları ve yorumları destekler

```
api-anahtarınız-1
api-anahtarınız-2
# Bu bir yorum satırıdır, göz ardı edilecektir

başka-bir-api-anahtarı
```

**Otomatik Oluşturma**: `key.txt` dosyası mevcut değilse, sistem otomatik olarak boş bir dosya oluşturur

### Anahtar Yönetim Yöntemleri

#### Dosyayı Manuel Olarak Düzenleme

Anahtar eklemek veya silmek için `key.txt` dosyasını doğrudan düzenleyin:

```bash
# Anahtar ekle
echo "yeni-api-anahtarınız" >> key.txt

# Mevcut anahtarları görüntüle (güvenliğe dikkat edin)
cat key.txt
```

#### Web Arayüzü Üzerinden Yönetim

Web Arayüzünün "Ayarlar" sekmesinde şunları yapabilirsiniz:

- Anahtar geçerliliğini doğrulama
- Sunucuda yapılandırılmış anahtar listesini görüntüleme (önce doğrulama gerekir)
- Belirli bir anahtarı test etme

### Anahtar Doğrulama Mekanizması

**Doğrulama Mantığı**:

- `key.txt` boşsa veya mevcut değilse, API anahtarı doğrulaması gerekmez
- Anahtarlar yapılandırılmışsa, tüm API istekleri geçerli bir anahtar gerektirir
- Anahtar doğrulama iki kimlik doğrulama başlığı biçimini destekler

**Güvenlik Özellikleri**:

- Anahtarlar günlüklerde maskelenmiş olarak gösterilir (ör: `abcd****efgh`)
- Web Arayüzündeki anahtar listesi de maskelenmiş olarak gösterilir
- Minimum uzunluk doğrulamasını destekler (en az 8 karakter)

## API Kimlik Doğrulama Süreci

### Bearer Token Kimlik Doğrulaması

Proje, standart OpenAI uyumlu kimlik doğrulama yöntemlerini destekler:

**Ana Kimlik Doğrulama Yöntemi** (önerilir):

```bash
Authorization: Bearer api-anahtarınız
```

**Alternatif Kimlik Doğrulama Yöntemi** (geriye dönük uyumluluk):

```bash
X-API-Key: api-anahtarınız
```

### Kimlik Doğrulama Davranışı

**Anahtar yapılandırması olmadığında**:

- Tüm API istekleri kimlik doğrulaması gerektirmez
- `/api/info` uç noktası `"api_key_required": false` gösterecektir

**Anahtar yapılandırması olduğunda**:

- `/v1/*` yolundaki tüm API istekleri geçerli bir anahtar gerektirir
- İstisnalar: `/v1/models`, `/health`, `/docs` gibi genel uç noktalar
- Kimlik doğrulama hatası `401 Unauthorized` hatası döndürür

### İstemci Yapılandırma Örneği

#### curl Örneği

```bash
# Bearer token kullanarak
curl -X POST http://127.0.0.1:2048/v1/chat/completions \
  -H "Authorization: Bearer api-anahtarınız" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Merhaba"}]}'

# X-API-Key başlığını kullanarak
curl -X POST http://127.0.0.1:2048/v1/chat/completions \
  -H "X-API-Key: api-anahtarınız" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Merhaba"}]}'
```

#### Python requests Örneği

```python
import requests

headers = {
    "Authorization": "Bearer api-anahtarınız",
    "Content-Type": "application/json"
}

data = {
    "messages": [{"role": "user", "content": "Merhaba"}]
}

response = requests.post(
    "http://127.0.0.1:2048/v1/chat/completions",
    headers=headers,
    json=data
)
```

## API Uç Noktaları

### Sohbet Arayüzü

**Uç Nokta**: `POST /v1/chat/completions`

- İstek gövdesi OpenAI API ile uyumludur, `messages` dizisi gerektirir.
- `model` alanı artık hedef modeli belirtmek için kullanılır, proxy AI Studio sayfasında o modele geçmeye çalışacaktır. Boşsa veya proxy'nin varsayılan model adıysa, AI Studio'da o anda etkin olan model kullanılır.
- `stream` alanı akışlı (`true`) veya akışsız (`false`) çıktıyı kontrol eder.
- Artık `temperature`, `max_output_tokens`, `top_p`, `stop` gibi parametreleri destekler, proxy bunları AI Studio sayfasında uygulamaya çalışacaktır.
- **Kimlik Doğrulaması Gerekli**: API anahtarları yapılandırılmışsa, bu uç nokta geçerli bir kimlik doğrulama başlığı gerektirir.

#### Örnek (curl, akışsız, parametrelerle)

```bash
curl -X POST http://127.0.0.1:2048/v1/chat/completions \
-H "Content-Type: application/json" \
-d '{
  "model": "gemini-1.5-pro-latest",
  "messages": [
    {"role": "system", "content": "Kısa ve öz ol."},
    {"role": "user", "content": "Fransa'nın başkenti neresidir?"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_output_tokens": 150,
  "top_p": 0.9,
  "stop": ["\n\nKullanıcı:"]
}'
```

#### Örnek (curl, akışlı, parametrelerle)

```bash
curl -X POST http://127.0.0.1:2048/v1/chat/completions \
-H "Content-Type: application/json" \
-d '{
  "model": "gemini-pro",
  "messages": [
    {"role": "user", "content": "Bir kedi hakkında kısa bir hikaye yaz."}
  ],
  "stream": true,
  "temperature": 0.9,
  "top_p": 0.95,
  "stop": []
}' --no-buffer
```

#### Örnek (Python requests)

```python
import requests
import json

API_URL = "http://127.0.0.1:2048/v1/chat/completions"
headers = {"Content-Type": "application/json"}
data = {
    "model": "gemini-1.5-flash-latest",
    "messages": [
        {"role": "user", "content": "'hello' kelimesini İspanyolca'ya çevir."}
    ],
    "stream": False, # veya akış için True
    "temperature": 0.5,
    "max_output_tokens": 100,
    "top_p": 0.9,
    "stop": ["\n\nİnsan:"]
}

response = requests.post(API_URL, headers=headers, json=data, stream=data["stream"])

if data["stream"]:
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                content = decoded_line[len('data: '):]
                if content.strip() == '[DONE]':
                    print("\nAkış bitti.")
                    break
                try:
                    chunk = json.loads(content)
                    delta = chunk.get('choices', [{}])[0].get('delta', {})
                    print(delta.get('content', ''), end='', flush=True)
                except json.JSONDecodeError:
                    print(f"\nJSON kodu çözülürken hata oluştu: {content}")
            elif decoded_line.startswith('data: {'): # Olası hata JSON'unu işle
                try:
                    error_data = json.loads(decoded_line[len('data: '):])
                    if 'error' in error_data:
                        print(f"\nSunucudan hata: {error_data['error']}")
                        break
                except json.JSONDecodeError:
                     print(f"\nHata JSON'u kodu çözülürken hata oluştu: {decoded_line}")
else:
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Hata: {response.status_code}\n{response.text}")
```

### Model Listesi

**Uç Nokta**: `GET /v1/models`

- AI Studio sayfasında algılanan kullanılabilir modellerin bir listesini ve proxy'nin kendisi için varsayılan bir model girişini döndürür.
- Artık AI Studio'dan dinamik olarak model listesini almaya çalışır. Alınamazsa, bir yedek model döndürür.
- Belirli model kimliklerini listeden çıkarmak için [`excluded_models.txt`](../excluded_models.txt) dosyasını destekler.
- **🆕 Betik Enjeksiyon Modelleri**: Betik enjeksiyonu özelliği etkinleştirilmişse, liste ayrıca userscript aracılığıyla enjekte edilen özel modelleri de içerir, bu modeller `"injected": true` olarak işaretlenir.

**Betik Enjeksiyon Modeli Özellikleri**:

- Model ID Formatı: Enjekte edilen modeller `models/` önekini otomatik olarak kaldırır, örneğin `models/kingfall-ab-test`, `kingfall-ab-test` olur
- Tanımlayıcı Alan: Tanımlama için `"injected": true` alanını içerir
- Sahip Tanımlayıcı: `"owned_by": "ai_studio_injected"`
- Tam Uyumlu: API aracılığıyla normal modeller gibi çağrılabilir

**Örnek Yanıt**:

```json
{
  "object": "list",
  "data": [
    {
      "id": "kingfall-ab-test",
      "object": "model",
      "created": 1703123456,
      "owned_by": "ai_studio_injected",
      "display_name": "👑 Kingfall",
      "description": "Kingfall modeli - Gelişmiş muhakeme yetenekleri",
      "injected": true
    }
  ]
}
```

### API Bilgileri

**Uç Nokta**: `GET /api/info`

- Temel URL ve model adı gibi API yapılandırma bilgilerini döndürür.

### Sağlık Kontrolü

**Uç Nokta**: `GET /health`

- Sunucu çalışma durumunu (Playwright, tarayıcı bağlantısı, sayfa durumu, Çalışan durumu, kuyruk uzunluğu) döndürür.

### Kuyruk Durumu

**Uç Nokta**: `GET /v1/queue`

- Mevcut istek kuyruğunun ayrıntılı bilgilerini döndürür.

### İsteği İptal Etme

**Uç Nokta**: `POST /v1/cancel/{req_id}`

- Hala kuyrukta işlenmeyi bekleyen bir isteği iptal etmeye çalışır.

### API Anahtarı Yönetim Uç Noktaları

#### Anahtar Listesini Al

**Uç Nokta**: `GET /api/keys`

- Sunucuda yapılandırılmış tüm API anahtarlarının bir listesini döndürür
- **Not**: Sunucu tam anahtarları döndürür, maskeleme Web Arayüzü ön ucu tarafından yapılır
- **Kimlik Doğrulaması Gerekmez**: Bu uç nokta API anahtarı kimlik doğrulaması gerektirmez

#### Anahtarı Test Et

**Uç Nokta**: `POST /api/keys/test`

- Belirtilen API anahtarının geçerli olup olmadığını doğrular
- İstek gövdesi: `{"key": "api-anahtarınız"}`
- Dönen değer: `{"success": true, "valid": true/false, "message": "..."}`
- **Kimlik Doğrulaması Gerekmez**: Bu uç nokta API anahtarı kimlik doğrulaması gerektirmez

#### Anahtar Ekle

**Uç Nokta**: `POST /api/keys`

- Sunucuya yeni bir API anahtarı ekler
- İstek gövdesi: `{"key": "yeni-api-anahtarınız"}`
- Anahtar gereksinimleri: en az 8 karakter, tekrar edemez
- **Kimlik Doğrulaması Gerekmez**: Bu uç nokta API anahtarı kimlik doğrulaması gerektirmez

#### Anahtarı Sil

**Uç Nokta**: `DELETE /api/keys`

- Sunucudan belirtilen API anahtarını siler
- İstek gövdesi: `{"key": "silinecek-anahtar"}`
- **Kimlik Doğrulaması Gerekmez**: Bu uç nokta API anahtarı kimlik doğrulaması gerektirmez

## İstemciyi Yapılandırma (Örnek olarak Open WebUI)

1. Open WebUI'yi açın.
2. "Ayarlar" -> "Bağlantılar" bölümüne gidin.
3. "Modeller" bölümünde, "Model Ekle"ye tıklayın.
4. **Model Adı**: İstediğiniz bir ad girin, örneğin `aistudio-gemini-py`.
5. **API Temel URL'si**: Proxy sunucusunun adresini girin, örneğin `http://127.0.0.1:2048/v1` (sunucu başka bir makinedeyse, `127.0.0.1`'i IP'siyle değiştirin ve bağlantı noktasının erişilebilir olduğundan emin olun).
6. **API Anahtarı**: Boş bırakın veya herhangi bir karakter girin (sunucu doğrulamaz).
7. Ayarları kaydedin.
8. Artık Open WebUI'de ilk adımda yapılandırdığınız model adını seçip sohbete başlayabilmelisiniz. Daha önce yapılandırdıysanız, yeni API temel adresini uygulamak için modeli yenilemeniz veya yeniden seçmeniz gerekebilir.

## Önemli İpuçları

### Üç Katmanlı Yanıt Alma Mekanizması ve Parametre Kontrolü

- **Yanıt Alma Önceliği**: Proje, yüksek kullanılabilirlik ve en iyi performansı sağlamak için üç katmanlı bir yanıt alma mekanizması kullanır:

  1. **Entegre Akış Proxy Hizmeti (Stream Proxy)**:
     - Varsayılan olarak etkindir, `3120` numaralı bağlantı noktasını dinler (`.env` dosyasının `STREAM_PORT` ile yapılandırılabilir)
     - En iyi performansı ve kararlılığı sağlar, AI Studio isteklerini doğrudan işler
     - Tarayıcı etkileşimi olmadan temel parametre geçişini destekler
  2. **Harici Yardımcı Hizmet**:
     - İsteğe bağlı yapılandırma, `--helper <endpoint_url>` parametresi veya `.env` yapılandırması ile etkinleştirilir
     - `SAPISID` Çerezini çıkarmak için geçerli bir kimlik doğrulama dosyası (`auth_profiles/active/*.json`) gerektirir
     - Akış proxy'sine bir yedek olarak hizmet eder
  3. **Playwright Sayfa Etkileşimi**:
     - Son yedek plan, tarayıcı otomasyonu yoluyla yanıtları alır
     - Tam parametre kontrolünü ve model değiştirmeyi destekler
     - Yanıtları almak için kullanıcı eylemlerini (düzenle/kopyala düğmeleri) simüle eder

- **Parametre Kontrolü Ayrıntıları**:

  - **Akış Proxy Modu**: Temel parametreleri (`model`, `temperature`, `max_tokens` vb.) destekler, en iyi performansı sunar
  - **Yardımcı Hizmet Modu**: Parametre desteği, harici Yardımcı hizmetinin özel uygulamasına bağlıdır
  - **Playwright Modu**: `temperature`, `max_output_tokens`, `top_p`, `stop`, `reasoning_effort`, `tools` vb. dahil olmak üzere tüm parametreleri tam olarak destekler

- **Model Yönetimi**:

  - API isteklerindeki `model` alanı, AI Studio sayfasında modeli değiştirmek için kullanılır
  - Dinamik model listesi alımını ve model kimliği doğrulamasını destekler
  - [`excluded_models.txt`](../excluded_models.txt) dosyası belirli model kimliklerini hariç tutabilir

- **🆕 Betik Enjeksiyonu Özelliği v3.0**:
  - Playwright yerel ağ kesintisini kullanır, %100 güvenilirlik
  - Yapılandırma dosyası bakımı olmadan model verilerini doğrudan userscript'ten ayrıştırır
  - Ön uç ve arka uç model verileri tamamen senkronize edilir, enjekte edilen modeller `"injected": true` olarak işaretlenir
  - Ayrıntılar için [Betik Enjeksiyon Kılavuzu](script_injection_guide.md) bölümüne bakın

### İstemci Tarafından Yönetilen Geçmiş

**İstemci geçmişi yönetir, proxy kullanıcı arayüzü içinde düzenlemeyi desteklemez**: İstemci, tam sohbet geçmişini sürdürmekten ve proxy'ye göndermekten sorumludur. Proxy sunucusunun kendisi, AI Studio arayüzündeki geçmiş mesajları düzenleme veya dallandırma işlemlerini desteklemez; her zaman istemci tarafından gönderilen tam mesaj listesini işler ve ardından AI Studio sayfasına gönderir.

## Uyumluluk Notları

### Python Sürüm Uyumluluğu

- **Önerilen Sürüm**: Python 3.10+ veya 3.11+ (üretim ortamı için önerilir)
- **Minimum Gereksinim**: Python 3.9 (tüm özellikler tam olarak desteklenir)
- **Docker Ortamı**: Python 3.10 (konteyner içindeki varsayılan sürüm)
- **Tam Destek**: Python 3.9, 3.10, 3.11, 3.12, 3.13
- **Bağımlılık Yönetimi**: Sürüm tutarlılığını sağlamak için Poetry kullanılır

### API Uyumluluğu

- **OpenAI API**: OpenAI v1 API standardıyla tam uyumlu, tüm ana istemcileri destekler
- **FastAPI**: 0.115.12 sürümüne dayanır, en son performans optimizasyonlarını ve özellik geliştirmelerini içerir
- **HTTP Protokolü**: HTTP/1.1 ve HTTP/2'yi destekler, tam asenkron işleme
- **Kimlik Doğrulama Yöntemleri**: Bearer Token ve X-API-Key başlık kimlik doğrulamasını destekler, OpenAI standardıyla uyumlu
- **Akışlı Yanıt**: Sunucu Tarafından Gönderilen Olaylar (SSE) akışlı çıktısını tam olarak destekler
- **FastAPI**: 0.111.0 sürümüne dayanır, modern asenkron özellikleri destekler
- **HTTP Protokolü**: HTTP/1.1 ve HTTP/2'yi destekler
- **Kimlik Doğrulama Yöntemleri**: Bearer Token ve X-API-Key başlık kimlik doğrulamasını destekler

## Sonraki Adımlar

API kullanım yapılandırması tamamlandıktan sonra, lütfen şunlara bakın:

- [Web UI Kullanım Kılavuzu](webui-guide.md)
- [Sorun Giderme Kılavuzu](troubleshooting.md)
- [Günlük Kontrol Kılavuzu](logging-control.md)