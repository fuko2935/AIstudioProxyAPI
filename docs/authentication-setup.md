# İlk Çalıştırma ve Kimlik Doğrulama Kurulum Kılavuzu

> **Not**: Proje şu anda varsayılan olarak Qwen misafir modunda çalışmaktadır (`ENABLE_QWEN_LOGIN_SUPPORT=false`), bu kılavuzdaki adımlardan herhangi birini gerçekleştirmenize gerek yoktur. Yalnızca `ENABLE_QWEN_LOGIN_SUPPORT=true`'yi açıkça etkinleştirdiyseniz ve manuel olarak oturum açmanız gerekiyorsa, aşağıdaki talimatlara başvurmanız gerekir.

Her başlatmada AI Studio'da manuel olarak oturum açmaktan kaçınmak için, önce bir kimlik doğrulama dosyası oluşturmak üzere [`launch_camoufox.py --debug`](../launch_camoufox.py) modunu veya [`gui_launcher.py`](../gui_launcher.py)'nin başlıklı modunu bir kez çalıştırmanız gerekir.

## Kimlik Doğrulama Dosyasının Önemi

**Kimlik doğrulama dosyası başsız modun anahtarıdır**: Başsız mod, oturum açma durumunu ve erişim izinlerini korumak için `auth_profiles/active/` dizinindeki geçerli `.json` dosyalarına dayanır. **Dosyaların süresi dolabilir** ve yeni kimlik doğrulama dosyalarını değiştirmek ve güncellemek için [`launch_camoufox.py --debug`](../launch_camoufox.py) modunu manuel olarak çalıştırarak, oturum açarak ve kaydederek düzenli olarak güncellenmesi gerekir.

## Yöntem Bir: Komut Satırı Aracılığıyla Hata Ayıklama Modunu Çalıştırma

**.env yapılandırma yöntemini kullanmanız önerilir**:
```env
# .env dosya yapılandırması
DEFAULT_FASTAPI_PORT=2048
STREAM_PORT=0
LAUNCH_MODE=normal
DEBUG_LOGS_ENABLED=true
```

```bash
# Basitleştirilmiş başlatma komutu (önerilir)
python launch_camoufox.py --debug

# Geleneksel komut satırı yöntemi (hala desteklenmektedir)
python launch_camoufox.py --debug --server-port 2048 --stream-port 0 --helper '' --internal-camoufox-proxy ''
```

**Önemli Parametre Açıklamaları:**
*   `--debug`: İlk kimlik doğrulama ve hata ayıklama için başlıklı modu başlatır
*   `--server-port <port_number>`: FastAPI sunucusunun dinleyeceği bağlantı noktasını belirtir (varsayılan: 2048)
*   `--stream-port <port_number>`: Entegre akış proxy hizmeti bağlantı noktasını başlatır (varsayılan: 3120). Bu hizmeti devre dışı bırakmak için `0` olarak ayarlayın, ilk başlatma için devre dışı bırakılması önerilir
*   `--helper <endpoint_url>`: Harici bir Yardımcı hizmetinin adresini belirtir. Harici bir Yardımcı kullanmamak için boş bir dize `''` olarak ayarlayın
*   `--internal-camoufox-proxy <proxy_address>`: Camoufox tarayıcısı için bir proxy belirtir. Proxy kullanmamak için boş bir dize `''` olarak ayarlayın
*   **Not**: Akış proxy hizmetini etkinleştirmeniz gerekiyorsa, normal çalışmayı sağlamak için `--internal-camoufox-proxy` parametresini de yapılandırmanız önerilir

### İşlem Adımları

1. Betik, Camoufox'u başlatır (kendisini dahili olarak çağırarak) ve terminalde başlatma bilgilerini yazdırır.
2. **Arayüzlü bir Firefox tarayıcı penceresinin** açıldığını göreceksiniz.
3. **Kritik Etkileşim:** **Açılan tarayıcı penceresinde Google ile oturum açın**, AI Studio sohbet arayüzünü görene kadar. (Betik, tarayıcı bağlantısını otomatik olarak yönetir, kullanıcı tarafından manuel işlem gerekmez).
4. **Oturum Açma Onay İşlemi**: Sistem bir oturum açma sayfası algıladığında ve terminalde aşağıdakine benzer bir istem görüntülendiğinde:
   ```
   Oturum açma gerekebilir. Tarayıcı bir oturum açma sayfası görüntülüyorsa, lütfen tarayıcı penceresinde Google ile oturum açın ve ardından devam etmek için burada Enter tuşuna basın...
   ```
   **Kullanıcının devam etmek için terminalde Enter tuşuna basarak işlemi onaylaması gerekir**. Bu onay adımı gereklidir ve sistem, bir sonraki oturum açma durumu kontrolüne geçmeden önce kullanıcının onay girişini bekleyecektir.
5. Terminale geri dönün ve istemlere göre Enter'a basın. Otomatik olmayan kaydetme modunu kullanacak şekilde ayarlanmışsa (kullanımdan kaldırılacak), kimlik doğrulamasını kaydederken istemlere göre `y` yazın ve Enter'a basın (dosya adı varsayılan olabilir). Dosya `auth_profiles/saved/` içine kaydedilecektir.
6. **`auth_profiles/saved/` altındaki yeni oluşturulan `.json` dosyasını `auth_profiles/active/` dizinine taşıyın.** `active` dizininde yalnızca bir `.json` dosyası olduğundan emin olun.
7. `--debug` modunun çalışmasını durdurmak için `Ctrl+C` tuşlarına basabilirsiniz.

## Yöntem İki: GUI Aracılığıyla Başlıklı Modu Başlatma

1. `python gui_launcher.py` komutunu çalıştırın.
2. GUI'de `FastAPI Hizmet Bağlantı Noktasını` girin (varsayılan 2048'dir).
3. `Başlıklı Modu Başlat` düğmesine tıklayın.
4. Açılan yeni konsol ve tarayıcı penceresinde, Google ile oturum açmak ve kimlik doğrulama dosyasını kaydetmek için komut satırı yöntemindeki istemleri izleyin.
5. Başsız modun normal şekilde kullanılabilmesi için kimlik doğrulama dosyasını `auth_profiles/saved/` dizininden `auth_profiles/active/` dizinine manuel olarak taşımanız da gerekir.

## Kimlik Doğrulama Dosyasını Etkinleştirme

1. `auth_profiles/saved/` dizinine gidin ve az önce kaydettiğiniz `.json` kimlik doğrulama dosyasını bulun.
2. Bu `.json` dosyasını `auth_profiles/active/` dizinine **taşıyın veya kopyalayın**.
3. **Önemli:** `auth_profiles/active/` dizininde **yalnızca bir `.json` dosyası olduğundan emin olun**. Başsız mod başlatıldığında bu dizindeki ilk `.json` dosyasını otomatik olarak yükleyecektir.

## Kimlik Doğrulama Dosyası Süresinin Dolması İşlemi

**Kimlik doğrulama dosyalarının süresi dolar!** Google'ın oturum açma durumu kalıcı değildir. Başsız mod başlatılamadığında ve bir kimlik doğrulama hatası bildirdiğinde veya oturum açma sayfasına yönlendirildiğinde, `active` dizinindeki kimlik doğrulama dosyasının süresinin dolduğu anlamına gelir. Şunları yapmanız gerekir:

1. `active` dizinindeki eski dosyayı silin.
2. Yeni bir kimlik doğrulama dosyası oluşturmak için yukarıdaki **[Komut Satırı Aracılığıyla Hata Ayıklama Modunu Çalıştırma]** veya **[GUI Aracılığıyla Başlıklı Modu Başlatma]** adımlarını yeniden gerçekleştirin.
3. Yeni oluşturulan `.json` dosyasını tekrar `active` dizinine taşıyın.

## Önemli İpuçları

*   **Yeni bir ana bilgisayara ilk erişimde performans sorunları**: Akış proxy'si aracılığıyla yeni bir HTTPS ana bilgisayarına ilk kez erişildiğinde, hizmetin o ana bilgisayar için dinamik olarak yeni bir alt sertifika oluşturması ve imzalaması gerekir. Bu işlem zaman alıcı olabilir, bu da o yeni ana bilgisayara ilk bağlantı isteğinin yavaş yanıt vermesine ve hatta bazı durumlarda ana program (örneğin [`server.py`](../server.py)'deki Playwright etkileşim mantığı) tarafından tarayıcı yükleme zaman aşımı olarak yanlış yorumlanmasına neden olabilir. Sertifika oluşturulup önbelleğe alındıktan sonra, aynı ana bilgisayara sonraki erişimler önemli ölçüde hızlanacaktır.

## Sonraki Adımlar

Kimlik doğrulama kurulumu tamamlandıktan sonra, lütfen şunlara bakın:
- [Günlük Kullanım Kılavuzu](daily-usage.md)
- [API Kullanım Kılavuzu](api-usage.md)
- [Web UI Kullanım Kılavuzu](webui-guide.md)