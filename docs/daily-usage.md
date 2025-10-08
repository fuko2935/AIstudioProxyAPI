# Günlük Kullanım Kılavuzu

Bu kılavuz, ilk kimlik doğrulama kurulumunu tamamladıktan sonra günlük işlemlerin nasıl yapılacağını açıklar. Proje, çeşitli başlatma yöntemleri sunar ve `.env` yapılandırma dosyasına dayalı basitleştirilmiş başlatma yönteminin kullanılması önerilir.

## Genel Bakış

İlk kimlik doğrulama kurulumunu tamamladıktan sonra, günlük işlemler için aşağıdaki yöntemlerden birini seçebilirsiniz:

- **Grafik Arayüz ile Başlatma**: [`gui_launcher.py`](../gui_launcher.py) tarafından sağlanan modern GUI arayüzünü kullanın
- **Komut Satırından Başlatma**: Doğrudan [`launch_camoufox.py`](../launch_camoufox.py) komut satırı aracını kullanın
- **Docker Dağıtımı**: Konteynerleştirilmiş dağıtım yöntemini kullanın

## ⭐ Basitleştirilmiş Başlatma Yöntemi (Önerilen)

**.env` yapılandırma dosyasına dayalı birleşik yapılandırma yönetimi ile başlatma son derece basit hale gelir!**

### Yapılandırma Avantajları

- ✅ **Bir kez yapılandır, ömür boyu kullan**: `.env` dosyasını yapılandırdıktan sonra başlatma komutları son derece basittir
- ✅ **Sürüm güncellemeleri sorunsuz**: `git pull`'dan sonra yeniden yapılandırmaya gerek yok, doğrudan başlatın
- ✅ **Parametrelerin merkezi yönetimi**: Tüm yapılandırma öğeleri `.env` dosyasında birleştirilmiştir
- ✅ **Ortam yalıtımı**: Farklı ortamlar için farklı yapılandırma dosyaları kullanılabilir

### Temel Başlatma (Önerilen)

```bash
# Grafik arayüz ile başlatma (yeni başlayanlar için önerilir)
python gui_launcher.py

# Komut satırından başlatma (günlük kullanım için önerilir)
python launch_camoufox.py --headless

# Hata ayıklama modu (ilk kurulum veya sorun giderme)
python launch_camoufox.py --debug
```

**İşte bu kadar basit!** Tüm yapılandırmalar `.env` dosyasında önceden ayarlanmıştır, karmaşık komut satırı parametrelerine gerek yoktur.

## Başlatıcı Açıklaması

### `--virtual-display` Hakkında (Linux Sanal Ekran Başsız Modu)

*   **Neden kullanılır?** Standart başsız modla karşılaştırıldığında, sanal ekran modu, tarayıcıyı çalıştırmak için tam bir sanal X sunucusu ortamı (Xvfb) oluşturur. Bu, daha gerçekçi bir masaüstü ortamını simüle edebilir, bu da bir web sitesi tarafından otomasyon betiği veya bot olarak algılanma riskini daha da azaltabilir, özellikle parmak izi ve algılama önleme için daha yüksek gereksinimleri olan senaryolar için uygundur ve aynı zamanda masaüstü olmayan bir ortamda hizmetin normal şekilde çalışmasını sağlar.
*   **Ne zaman kullanılır?** Linux ortamında çalışırken ve başsız modda çalışmak istediğinizde.
*   **Nasıl kullanılır?**
    1. Linux sisteminizde `xvfb`'nin kurulu olduğundan emin olun ([Kurulum Kılavuzu](installation-guide.md)'ndaki kurulum talimatlarına bakın).
    2. [`launch_camoufox.py`](../launch_camoufox.py) çalıştırırken `--virtual-display` bayrağını ekleyin. Örneğin:
        ```bash
        python launch_camoufox.py --virtual-display --server-port 2048 --stream-port 3120 --internal-camoufox-proxy ''
        ```

## Proxy Yapılandırma Önceliği

Proje, proxy ayarlarını belirlemek için aşağıdaki öncelik sırasına göre birleşik bir proxy yapılandırma yönetim sistemi kullanır:

1. **`--internal-camoufox-proxy` komut satırı parametresi** (en yüksek öncelik)
   - Proxy'yi açıkça belirtin: `--internal-camoufox-proxy 'http://127.0.0.1:7890'`
   - Proxy'yi açıkça devre dışı bırakın: `--internal-camoufox-proxy ''`
2. **`UNIFIED_PROXY_CONFIG` ortam değişkeni** (önerilen, .env dosyası yapılandırması)
3. **`HTTP_PROXY` ortam değişkeni**
4. **`HTTPS_PROXY` ortam değişkeni**
5. **Sistem proxy ayarları** (Linux altında gsettings, en düşük öncelik)

**Önerilen yapılandırma yöntemi**:
```env
# .env dosyasında proxy'yi birleşik olarak yapılandırın
UNIFIED_PROXY_CONFIG=http://127.0.0.1:7890
# veya proxy'yi devre dışı bırakın
UNIFIED_PROXY_CONFIG=
```

**Önemli Not**: Bu proxy yapılandırması, tüm sistemin proxy davranışının tutarlı olmasını sağlamak için hem Camoufox tarayıcısına hem de akış proxy hizmetinin yukarı akış bağlantılarına uygulanacaktır.

## Üç Katmanlı Yanıt Alma Mekanizması Yapılandırması

Proje, yüksek kullanılabilirlik ve en iyi performansı sağlamak için üç katmanlı bir yanıt alma mekanizması kullanır. Ayrıntılı açıklamalar için lütfen [Akış İşleme Modları Ayrıntılı Açıklaması](streaming-modes.md)'na bakın.

### Mod 1: Entegre Akış Proxy'sini Önceliklendirme (Varsayılan Önerilen)

**`.env` yapılandırmasını kullanma (önerilir):**

```env
# .env dosyasında yapılandırın
STREAM_PORT=3120
UNIFIED_PROXY_CONFIG=http://127.0.0.1:7890  # Gerekirse proxy
```

```bash
# Sonra basitçe başlatın
python launch_camoufox.py --headless
```

**Komut satırı geçersiz kılma (ileri düzey kullanıcılar):**

```bash
# Özel akış proxy bağlantı noktası kullanın
python launch_camoufox.py --headless --stream-port 3125

# Proxy yapılandırmasını etkinleştirin
python launch_camoufox.py --headless --internal-camoufox-proxy 'http://127.0.0.1:7890'

# Proxy'yi açıkça devre dışı bırakın (.env'deki ayarları geçersiz kılar)
python launch_camoufox.py --headless --internal-camoufox-proxy ''
```

Bu modda, ana sunucu önce `3120` numaralı bağlantı noktasındaki (veya `.env`'de yapılandırılan `STREAM_PORT`) entegre akış proxy'si aracılığıyla yanıtı almayı dener. Başarısız olursa, Playwright sayfa etkileşimine geri döner.

### Mod 2: Harici Yardımcı Hizmeti Önceliklendirme (Entegre Akış Proxy'sini Devre Dışı Bırakma)

**`.env` yapılandırmasını kullanma (önerilir):**

```bash
# .env dosyasında yapılandırın
STREAM_PORT=0  # Entegre akış proxy'sini devre dışı bırak
GUI_DEFAULT_HELPER_ENDPOINT=http://your-helper-service.com/api/getStreamResponse

# Sonra basitçe başlatın
python launch_camoufox.py --headless
```

**Komut satırı geçersiz kılma (ileri düzey kullanıcılar):**

```bash
# Harici Yardımcı modu
python launch_camoufox.py --headless --stream-port 0 --helper 'http://your-helper-service.com/api/getStreamResponse'
```

Bu modda, ana sunucu önce Yardımcı uç noktası aracılığıyla yanıtı almayı dener (`SAPISID`'yi çıkarmak için geçerli `auth_profiles/active/*.json` gerekir). Başarısız olursa, Playwright sayfa etkileşimine geri döner.

### Mod 3: Yalnızca Playwright Sayfa Etkileşimini Kullanma (Tüm Akış Proxy'lerini ve Yardımcıları Devre Dışı Bırakma)

**`.env` yapılandırmasını kullanma (önerilir):**

```bash
# .env dosyasında yapılandırın
STREAM_PORT=0  # Entegre akış proxy'sini devre dışı bırak
GUI_DEFAULT_HELPER_ENDPOINT=  # Yardımcı hizmeti devre dışı bırak

# Sonra basitçe başlatın
python launch_camoufox.py --headless
```

**Komut satırı geçersiz kılma (ileri düzey kullanıcılar):**

```bash
# Saf Playwright modu
python launch_camoufox.py --headless --stream-port 0 --helper ''
```

Bu modda, ana sunucu yanıtı almak için yalnızca Playwright aracılığıyla AI Studio sayfasıyla etkileşime girecektir ("Düzenle" veya "Kopyala" düğmelerine tıklamayı simüle ederek). Bu, geleneksel bir geri dönüş yöntemidir.

## Grafik Arayüz Başlatıcısını Kullanma

Proje, Tkinter tabanlı bir grafik kullanıcı arayüzü (GUI) başlatıcısı sağlar: [`gui_launcher.py`](../gui_launcher.py).

### GUI'yi Başlatma

```bash
python gui_launcher.py
```

### GUI Özellikleri

*   **Hizmet Bağlantı Noktası Yapılandırması**: FastAPI sunucusunun dinleyeceği bağlantı noktası numarasını belirtin (varsayılan 2048).
*   **Bağlantı Noktası İşlem Yönetimi**: Belirtilen bağlantı noktasındaki işlemleri sorgulayın ve durdurun.
*   **Başlatma Seçenekleri**:
    1. **Başlıklı Modu Başlat (Hata Ayıklama, Etkileşimli)**: `python launch_camoufox.py --debug`'a karşılık gelir
    2. **Başsız Modu Başlat (Arka Planda Bağımsız Çalışma)**: `python launch_camoufox.py --headless`'a karşılık gelir
*   **Yerel LLM Simülasyon Hizmeti**: Yerel LLM simülasyon hizmetini başlatın ve yönetin ([`llm.py`](../llm.py) tabanlı)
*   **Durum ve Günlükler**: Hizmet durumunu ve gerçek zamanlı günlükleri görüntüleyin

### Kullanım Önerileri

*   İlk çalıştırma veya kimlik doğrulama dosyasını güncelleme ihtiyacı: "Başlıklı Modu Başlat"ı kullanın
*   Günlük arka plan çalışması: "Başsız Modu Başlat"ı kullanın
*   Ayrıntılı günlükler veya hata ayıklama ihtiyacı: Doğrudan komut satırını kullanın [`launch_camoufox.py`](../launch_camoufox.py)

## Önemli Notlar

### Yapılandırma Önceliği

1. **`.env` dosya yapılandırması** - Önerilen yapılandırma yöntemi, bir kez ayarlayın ve uzun süre kullanın
2. **Komut satırı parametreleri** - `.env` dosyasındaki ayarları geçersiz kılabilir, geçici ayarlamalar için uygundur
3. **Ortam değişkenleri** - En düşük öncelik, esas olarak sistem düzeyinde yapılandırma için kullanılır

### Kullanım Önerileri

- **Günlük kullanım**: `.env` dosyasını yapılandırdıktan sonra, basit `python launch_camoufox.py --headless` yeterlidir
- **Geçici ayarlamalar**: Yapılandırmayı geçici olarak değiştirmeniz gerektiğinde, `.env` dosyasını değiştirmeden komut satırı parametrelerini kullanarak geçersiz kılın
- **İlk kurulum**: Kimlik doğrulama kurulumu için `python launch_camoufox.py --debug` kullanın

**Yalnızca hata ayıklama modunu kullanarak her şeyin normal çalıştığını (özellikle tarayıcı içi oturum açma ve kimlik doğrulama kaydı) ve `auth_profiles/active/` dizininde geçerli bir kimlik doğrulama dosyası olduğunu onayladıktan sonra, başsız modu günlük arka plan çalışması için standart bir yol olarak kullanmanız önerilir.**

## Sonraki Adımlar

Günlük çalışma ayarları tamamlandıktan sonra, lütfen şunlara bakın:
- [API Kullanım Kılavuzu](api-usage.md)
- [Web UI Kullanım Kılavuzu](webui-guide.md)
- [Sorun Giderme Kılavuzu](troubleshooting.md)