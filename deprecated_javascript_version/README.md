# AI Studio Proxy Sunucusu (Javascript Sürümü - KULLANIMDAN KALDIRILDI)

**⚠️ Uyarı: Bu Javascript sürümü (`server.cjs`, `auto_connect_aistudio.cjs`) kullanımdan kaldırılmıştır ve artık bakımı yapılmamaktadır. Proje kök dizinindeki, modüler bir mimari tasarıma sahip, daha iyi kararlılık ve sürdürülebilirlik sunan Python sürümünü kullanmanız önerilir.**

**📖 En Son Belgeleri Görüntüleyin**: Mevcut Python sürümünün tam kullanım talimatları için lütfen proje kök dizinindeki [`README.md`](../README.md) dosyasına bakın.

---

[Proje kullanım tanıtım videosunu izlemek için tıklayın](https://drive.google.com/file/d/1efR-cNG2CNboNpogHA1ASzmx45wO579p/view?usp=drive_link)

Bu, Google AI Studio web sürümüne OpenAI API'sini taklit ederek erişen bir Node.js + Playwright sunucusudur ve Gemini konuşmalarını sorunsuz bir şekilde iletir. Bu, OpenAI API uyumlu istemcilerin (Open WebUI, NextChat vb.) AI Studio'nun sınırsız kotasını ve yeteneklerini kullanmasını sağlar.

## ✨ Özellikler (Javascript Sürümü)

*   **OpenAI API Uyumluluğu**: Çoğu OpenAI istemcisiyle uyumlu `/v1/chat/completions` ve `/v1/models` uç noktaları sağlar.
*   **Akışlı Yanıt**: Daktilo efekti için `stream=true` destekler.
*   **Akışsız Yanıt**: Tam JSON yanıtını tek seferde döndürmek için `stream=false` destekler.
*   **Sistem İstemcisi (System Prompt)**: İstek gövdesindeki `messages` dizisinin `system` rolü veya ek `system_prompt` alanı aracılığıyla sistem istemcisi iletmeyi destekler.
*   **Dahili Prompt Optimizasyonu**: AI Studio'yu belirli bir formatta (akışlı için Markdown kod bloğu, akışsız için JSON) çıktı vermesi için yönlendirmek ve ayrıştırma için bir başlangıç ​​işaretçisi `<<<START_RESPONSE>>>` eklemek üzere kullanıcı girdisini otomatik olarak sarar.
*   **Otomatik Bağlantı Betiği (`auto_connect_aistudio.cjs`)**:
    *   Chrome/Chromium tarayıcısını otomatik olarak bulur ve başlatır, bir hata ayıklama bağlantı noktası açar ve **"Sohbeti temizle" düğmesinin görünür olmasını sağlamak için belirli bir pencere genişliği (460 piksel) ayarlar**.
    *   Mevcut Chrome hata ayıklama örneklerini otomatik olarak algılar ve bağlanmaya çalışır.
    *   Kullanıcıların mevcut bir örneğe bağlanmayı veya çakışan işlemleri otomatik olarak sonlandırmayı seçmelerine olanak tanıyan etkileşimli seçenekler sunar.
    *   AI Studio'nun `Yeni sohbet` sayfasını otomatik olarak bulur veya açar.
    *   `server.cjs`'yi otomatik olarak başlatır.
*   **Sunucu Tarafı (`server.cjs`)**:
    *   `auto_connect_aistudio.cjs` tarafından yönetilen Chrome örneğine bağlanır.
    *   **Bağlamı Otomatik Temizleme**: İstemciden gelen bir isteğin "yeni bir konuşma" olabileceğini algıladığında (mesaj geçmişi uzunluğuna göre), daha iyi oturum yalıtımı sağlamak için AI Studio sayfasındaki "Sohbeti Temizle" düğmesine ve onay iletişim kutusuna tıklamayı otomatik olarak simüle eder ve temizleme etkisini doğrular.
    *   API isteklerini işler, Playwright aracılığıyla AI Studio sayfasını çalıştırır.
    *   AI Studio'nun yanıtını ayrıştırır, geçerli içeriği çıkarır.
    *   Temel testler için basit bir Web Arayüzü (`/`) sağlar.
    *   Bir sağlık kontrolü uç noktası (`/health`) sağlar.
*   **Hata Anlık Görüntüleri**: Playwright işlemleri, yanıt ayrıştırma veya **sohbeti temizleme** sırasında bir hata oluştuğunda, hata ayıklamayı kolaylaştırmak için proje kök dizininin altındaki `errors/` dizinine otomatik olarak sayfa ekran görüntülerini ve HTML'yi kaydeder. (Not: Python sürümü hata anlık görüntüleri `errors_py/` içindedir)
*   **Bağımlılık Tespiti**: Her iki betik de başlatıldığında gerekli bağımlılıkları kontrol eder ve kurulum talimatları sağlar.
*   **Çapraz Platform Tasarımı**: macOS, Linux ve Windows'u (WSL önerilir) desteklemek üzere tasarlanmıştır.

## ⚠️ Önemli Notlar (Javascript Sürümü)

*   **Resmi Olmayan Proje**: Bu projenin Google ile hiçbir ilgisi yoktur ve AI Studio Web arayüzünün otomasyonuna dayanır, bu da AI Studio sayfa güncellemeleri nedeniyle bozulabilir.
*   **Otomatik Temizleme İşlevinin Kırılganlığı**: Bağlamı otomatik temizleme işlevi, `server.cjs`'deki hassas UI öğe seçicilerine (`CLEAR_CHAT_BUTTON_SELECTOR`, `CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR`) dayanır. AI Studio sayfa yapısı değişirse, bu işlev başarısız olabilir. Bu durumda bu seçicilerin güncellenmesi gerekir.
*   **Geçmiş Düzenleme/Dallandırma Desteği Yok**: Yeni konuşmalar için bağlam temizliği uygulansa bile, bu proxy istemcinin geçmiş mesajları düzenlemesini ve o noktadan itibaren konuşmayı yeniden oluşturmasını hala destekleyemez. AI Studio'nun dahili olarak sürdürdüğü konuşma geçmişi doğrusaldır.
*   **Sabit Pencere Genişliği**: `auto_connect_aistudio.cjs`, temizleme düğmesinin görünür olmasını sağlamak için Chrome penceresini sabit bir genişlikte (460 piksel) başlatır.
*   **Güvenlik**: Chrome'u başlatmak, uzak bir hata ayıklama bağlantı noktası (varsayılan olarak `8848`) açar. Lütfen bu bağlantı noktasının yalnızca güvenilir bir ağ ortamında kullanıldığından emin olun veya güvenlik duvarı kurallarıyla erişimi kısıtlayın. Bu bağlantı noktasını asla genel internete maruz bırakmayın.
*   **Kararlılık**: Tarayıcı otomasyonuna dayandığı için kararlılığı resmi bir API kadar iyi değildir. Uzun süreli çalışma veya sık istekler sayfanın yanıt vermemesine veya bağlantının kesilmesine neden olabilir, bu da tarayıcının veya sunucunun yeniden başlatılmasını gerektirebilir.
*   **AI Studio Sınırlamaları**: AI Studio'nun kendisinin istek sıklığı sınırlamaları, içerik politikası kısıtlamaları vb. olabilir ve proxy sunucusu bu sınırlamaları aşamaz.
*   **Parametre Yapılandırması**: **Model seçimi, sıcaklık, çıktı uzunluğu gibi parametrelerin doğrudan AI Studio sayfasının sağ tarafındaki ayarlar panelinde ayarlanması gerekir. Bu proxy sunucusu şu anda API istekleri aracılığıyla iletilen bu parametreleri işlemez veya iletmez.** Gerekli modeli ve parametreleri AI Studio Web Arayüzünde önceden ayarlamanız gerekir.

## 🛠️ Yapılandırma (Javascript Sürümü)

Sık sık değiştirilmesi önerilmese de, aşağıdaki sabitleri anlamak betik davranışını anlamanıza veya özel durumlarda ayarlamalar yapmanıza yardımcı olabilir:

**`auto_connect_aistudio.cjs`:**

*   `DEBUGGING_PORT`: (varsayılan `8848`) Chrome tarayıcısı başlatıldığında kullanılan uzak hata ayıklama bağlantı noktası.
*   `TARGET_URL`: (varsayılan `'https://aistudio.google.com/prompts/new_chat'`) Betiğin açmaya veya gezinmeye çalıştığı AI Studio sayfası.
*   `SERVER_SCRIPT_FILENAME`: (varsayılan `'server.cjs'`) Bu betik tarafından otomatik olarak başlatılan API sunucusu dosya adı.
*   `CONNECT_TIMEOUT_MS`: (varsayılan `20000`) Chrome hata ayıklama bağlantı noktasına bağlanma zaman aşımı (milisaniye).
*   `NAVIGATION_TIMEOUT_MS`: (varsayılan `35000`) Playwright'ın sayfa gezinmesinin tamamlanmasını bekleme zaman aşımı (milisaniye).
*   `--window-size=460,...`: UI öğelerinin (temizleme düğmesi gibi) konumunun nispeten kararlı olmasını sağlamak için Chrome başlatılırken iletilen parametre.

**`server.cjs`:**

*   `SERVER_PORT`: (varsayılan `2048`) API sunucusunun dinlediği bağlantı noktası.
*   `AI_STUDIO_URL_PATTERN`: (varsayılan `'aistudio.google.com/'`) AI Studio sayfasını tanımlamak için kullanılan URL parçası.
*   `RESPONSE_COMPLETION_TIMEOUT`: (varsayılan `300000`) AI Studio yanıtının tamamlanmasını beklemek için toplam zaman aşımı (milisaniye, 5 dakika).
*   `POLLING_INTERVAL`: (varsayılan `300`) AI Studio sayfa durumunu kontrol etme aralığı (milisaniye).
*   `SILENCE_TIMEOUT_MS`: (varsayılan `3000`) AI Studio'nun çıktı vermeyi durdurup durdurmadığını belirlemek için sessizlik zaman aşımı (milisaniye).
*   `CLEAR_CHAT_VERIFY_TIMEOUT_MS`: (varsayılan `5000`) Sohbeti temizleme işleminin tamamlanmasını beklemek ve doğrulamak için zaman aşımı (milisaniye).
*   **CSS Seçicileri**: (`INPUT_SELECTOR`, `SUBMIT_BUTTON_SELECTOR`, `RESPONSE_CONTAINER_SELECTOR`, `LOADING_SPINNER_SELECTOR`, `ERROR_TOAST_SELECTOR`, `CLEAR_CHAT_BUTTON_SELECTOR`, `CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR`) Bu sabitler, betiğin sayfa öğelerini bulmak için kullandığı seçicileri tanımlar. **Bu değerleri değiştirmek ön uç bilgisi gerektirir ve AI Studio sayfası güncellenirse, bunlar ayarlanması en olası kısımlardır.**

## ⚙️ Prompt Dahili İşlemleri (Javascript Sürümü)

Proxy'nin AI Studio'nun çıktısını ayrıştırabilmesi için, `server.cjs` isteminizi AI Studio'ya göndermeden önce belirli talimatlar ekleyerek sarar ve AI'dan şunları ister:

1.  **Akışsız istekler için (`stream=false`)**: Tüm yanıtı `{"response": "<<<START_RESPONSE>>>[AI'nin gerçek yanıtı]"}` biçiminde bir JSON nesnesine sarın.
2.  **Akışlı istekler için (`stream=true`)**: Tüm yanıtı (başlangıç ​​ve bitiş dahil) bir Markdown kod bloğuna (```) sarın ve gerçek yanıttan önce `<<<START_RESPONSE>>>` işaretçisini ekleyin, örneğin:
    ```markdown
    ```
    <<<START_RESPONSE>>>[AI'nin gerçek yanıtının ilk kısmı]
    [AI'nin gerçek yanıtının ikinci kısmı]
    ...
    ```
    ```

`server.cjs`, gerçek yanıt içeriğini çıkarmak için `<<<START_RESPONSE>>>` işaretçisini arar. Bu, API aracılığıyla aldığınız yanıtın bu dahili işleme sürecinden geçtiği ve AI Studio sayfasının orijinal çıktı biçiminin değiştirileceği anlamına gelir.

## 🚀 Başlarken (Javascript Sürümü)

### 1. Ön Koşullar

*   **Node.js**: v16 veya üstü.
*   **NPM / Yarn / PNPM**: Bağımlılıkları yüklemek için.
*   **Google Chrome / Chromium**: Tarayıcının kendisinin kurulu olması gerekir.
*   **Google AI Studio Hesabı**: Ve normal şekilde erişilebilir ve kullanılabilir olmalıdır.

### 2. Kurulum

1.  **Kullanımdan kaldırılan sürüm dizinine girin**:
    ```bash
    cd deprecated_javascript_version
    ```

2.  **Bağımlılıkları yükleyin**:
    `package.json` dosyasına göre, betiğin çalışması için aşağıdaki temel bağımlılıklar gerekir:
    *   `express`: API sunucusu oluşturmak için kullanılan web çerçevesi.
    *   `cors`: Alanlar arası kaynak paylaşımını işler.
    *   `playwright`: Tarayıcı otomasyonu kütüphanesi.
    *   `@playwright/test`: Playwright'ın test kütüphanesi, `server.cjs` iddialar için `expect` işlevini kullanır.

    Paket yöneticinizi kullanarak yükleyin:
    ```bash
    npm install
    # veya
    yarn install
    # veya
    pnpm install
    ```

### 3. Çalıştırma

Tüm hizmetleri başlatmak için yalnızca `auto_connect_aistudio.cjs` betiğini çalıştırmanız yeterlidir:

```bash
node auto_connect_aistudio.cjs
```

Bu betik aşağıdaki işlemleri gerçekleştirir:

1.  **Bağımlılıkları kontrol et**: Yukarıdaki Node.js modüllerinin kurulu olduğunu ve `server.cjs` dosyasının mevcut olduğunu onaylar.
2.  **Chrome hata ayıklama bağlantı noktasını kontrol et (`8848`)**:
    *   Bağlantı noktası boşsa, yeni bir Chrome örneğini (pencere genişliği 460 piksel olarak sabitlenmiş) otomatik olarak bulmaya ve başlatmaya ve uzak hata ayıklama bağlantı noktasını açmaya çalışır.
    *   Bağlantı noktası meşgulse, kullanıcıya mevcut bir örneğe mi bağlanmak istediğini yoksa bağlantı noktasını temizledikten sonra yeni bir örnek mi başlatmak istediğini sorar.
3.  **Playwright'a bağlan**: Chrome'un hata ayıklama bağlantı noktasına (`http://127.0.0.1:8848`) bağlanmaya çalışır.
4.  **AI Studio sayfasını yönet**: AI Studio'nun `Yeni sohbet` sayfasını (`https://aistudio.google.com/prompts/new_chat`) bulur veya açar ve ön plana getirmeye çalışır.
5.  **API sunucusunu başlat**: Yukarıdaki adımlar başarılı olursa, betik arka planda otomatik olarak `node server.cjs`'yi başlatır.

`server.cjs` başarıyla başlatıldığında ve Playwright'a bağlandığında, terminalde aşağıdakine benzer bir çıktı göreceksiniz (`server.cjs`'den):

```
=============================================================
          🚀 AI Studio Proxy Sunucusu (vX.XX - Kuyruk ve Otomatik Temizleme) 🚀
=============================================================
🔗 Dinleme adresi: http://localhost:2048
   - Web Arayüzü (Test): http://localhost:2048/
   - API Uç Noktası:   http://localhost:2048/v1/chat/completions
   - Model Arayüzü:   http://localhost:2048/v1/models
   - Sağlık Kontrolü:   http://localhost:2048/health
-------------------------------------------------------------
✅ Playwright bağlantısı başarılı, hizmet hazır!
-------------------------------------------------------------
```
*(Sürüm numarası farklı olabilir)*

Bu noktada, proxy hizmeti `http://localhost:2048` adresinde dinlemeye hazırdır.

### 4. İstemciyi Yapılandırma (Örnek olarak Open WebUI)

1.  Open WebUI'yi açın.
2.  "Ayarlar" -> "Bağlantılar" bölümüne gidin.
3.  "Modeller" bölümünde, "Model Ekle"ye tıklayın.
4.  **Model Adı**: İstediğiniz bir ad girin, örneğin `aistudio-gemini-cjs`.
5.  **API Temel URL'si**: Proxy sunucusunun adresini girin, örneğin `http://localhost:2048/v1` (`/v1`'i dahil ettiğinizden emin olun).
6.  **API Anahtarı**: Boş bırakın veya herhangi bir karakter girin (sunucu doğrulamaz).
7.  Ayarları kaydedin.
8.  Artık Open WebUI'de `aistudio-gemini-cjs` modelini seçip sohbete başlayabilmelisiniz.

### 5. Test Betiğini Kullanma (İsteğe Bağlı)

Bu dizinde, komut satırında doğrudan proxy ile etkileşimli sohbet için bir `test.js` betiği bulunmaktadır.

1.  **Ek bağımlılıkları yükleyin**: `test.js`, OpenAI'nin resmi Node.js SDK'sını kullanır.
    ```bash
    npm install openai
    # veya yarn add openai / pnpm add openai
    ```
2.  **Yapılandırmayı kontrol edin**: `test.js`'yi açın ve `LOCAL_PROXY_URL`'nin proxy sunucu adresinize (`http://127.0.0.1:2048/v1/`) işaret ettiğini onaylayın. `DUMMY_API_KEY` olduğu gibi kalabilir.
3.  **Testi çalıştırın**: `deprecated_javascript_version` dizininde şunu çalıştırın:
    ```bash
    node test.js
    ```
    Ardından test için komut satırına sorular girebilirsiniz. Çıkmak için `exit` yazın.

## 💻 Çoklu Platform Kılavuzu (Javascript Sürümü)

*   **macOS**:
    *   `auto_connect_aistudio.cjs` genellikle Chrome'u otomatik olarak bulabilir.
    *   Güvenlik duvarı, Node.js'nin ağ bağlantılarını kabul edip etmemesini sorabilir, lütfen izin verin.
*   **Linux**:
    *   `google-chrome-stable` veya `chromium-browser`'ın kurulu olduğundan emin olun.
    *   Betik Chrome'u bulamazsa, `auto_connect_aistudio.cjs`'deki `getChromePath` işlevini manuel olarak yolu belirtmek için değiştirmeniz veya gerçek Chrome yürütülebilir dosyasına işaret eden bir sembolik bağlantı (`/usr/bin/google-chrome`) oluşturmanız gerekebilir.
    *   Bazı Linux dağıtımları ek Playwright bağımlılık kitaplıkları yüklemenizi gerektirebilir, [Playwright Linux belgelerine](https://playwright.dev/docs/intro#system-requirements) bakın. `npx playwright install-deps` komutunu çalıştırmak yüklemeye yardımcı olabilir.
*   **Windows**:
    *   **WSL (Windows Subsystem for Linux) kullanmanız şiddetle tavsiye edilir**. WSL'de Linux kılavuzunu takip etmek genellikle daha sorunsuzdur.
    *   **Doğrudan Windows'ta çalıştırma (önerilmez)**:
        *   `auto_connect_aistudio.cjs`'nin Chrome'un tam yolunu belirtmek için `getChromePath` işlevini manuel olarak değiştirmeniz gerekebilir (örneğin `C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe`). Yoldaki ters eğik çizgilerin kaçış karakteriyle (`\\`) yazılması gerektiğini unutmayın.
        *   Güvenlik duvarı ayarlarının Node.js ve Chrome'un bağlantı noktalarını (`8848` ve `2048`) dinlemesine ve bağlanmasına izin vermesi gerekir.
        *   Dosya sistemi ve izin farklılıkları nedeniyle, bağlantı noktası kontrolü veya işlem sonlandırma işlemleri (`taskkill`) gibi bilinmeyen sorunlarla karşılaşabilirsiniz.

## 🔧 Sorun Giderme (Javascript Sürümü)

*   **`auto_connect_aistudio.cjs` başlatılamıyor veya hata veriyor**:
    *   **Bağımlılık bulunamadı**: `npm install` gibi komutları çalıştırdığınızdan emin olun.
    *   **Chrome yolu bulunamadı**: Chrome/Chromium'un kurulu olduğundan emin olun ve gerektiğinde `getChromePath` işlevini değiştirin veya bir sembolik bağlantı oluşturun (Linux).
    *   **Bağlantı noktası (`8848`) meşgul ve otomatik olarak temizlenemiyor**: Betik istemlerine göre, bağlantı noktasını meşgul eden işlemi manuel olarak bulmak ve sonlandırmak için sistem araçlarını (örneğin `lsof -i :8848` / `tasklist | findstr "8848"`) kullanın.
    *   **Playwright'a bağlanma zaman aşımı**: Chrome'un başarıyla başlatıldığını ve `8848` numaralı bağlantı noktasını dinlediğini ve güvenlik duvarının yerel bağlantıyı `127.0.0.1:8848` engellemediğini onaylayın. `auto_connect_aistudio.cjs`'deki `CONNECT_TIMEOUT_MS`'nin yeterli olup olmadığını kontrol edin.
    *   **AI Studio sayfasını açma/gezinme başarısız**: Ağ bağlantısını kontrol edin, `https://aistudio.google.com/prompts/new_chat`'i tarayıcıda manuel olarak açmayı ve oturum açmayı deneyin. `NAVIGATION_TIMEOUT_MS`'nin yeterli olup olmadığını kontrol edin.
    *   **Pencere boyutu sorunu**: 460 piksel genişlik sorunlara neden oluyorsa, `auto_connect_aistudio.cjs`'deki `--window-size` parametresini değiştirmeyi deneyebilirsiniz, ancak bu otomatik temizleme işlevini etkileyebilir.
*   **`server.cjs` başlatıldığında bağlantı noktası meşgul hatası (`EADDRINUSE`)**:
    *   Başka bir programın (eski sunucu örnekleri dahil) `2048` numaralı bağlantı noktasını kullanıp kullanmadığını kontrol edin. Çakışan programı kapatın veya `server.cjs`'deki `SERVER_PORT`'u değiştirin.
*   **Sunucu günlüğü Playwright'ın hazır olmadığını veya bağlantının başarısız olduğunu gösteriyor (`server.cjs` başlatıldıktan sonra)**:
    *   Genellikle `auto_connect_aistudio.cjs` tarafından başlatılan Chrome örneğinin beklenmedik bir şekilde kapandığı veya yanıt vermediği anlamına gelir. Chrome penceresinin hala orada olup olmadığını ve AI Studio sayfasının çöküp çökmediğini kontrol edin.
    *   Tüm ilgili işlemleri (`node` ve `chrome`) kapatmayı ve ardından `node auto_connect_aistudio.cjs`'yi yeniden çalıştırmayı deneyin.
    *   Kök dizindeki `errors/` dizininde ekran görüntüleri ve HTML dosyaları olup olmadığını kontrol edin, bunlar AI Studio sayfasının hata mesajlarını veya durumunu içerebilir.
*   **İstemci (örneğin Open WebUI) bağlanamıyor veya istek başarısız oluyor**:
    *   API temel URL'sinin doğru yapılandırıldığını onaylayın (`http://localhost:2048/v1`).
    *   `server.cjs`'nin çalıştığı terminalde hata çıktısı olup olmadığını kontrol edin.
    *   İstemcinin ve sunucunun aynı ağda olduğundan ve güvenlik duvarının istemciden sunucunun `2048` numaralı bağlantı noktasına bağlantıyı engellemediğinden emin olun.
*   **API isteği 5xx hatası döndürüyor**:
    *   **503 Service Unavailable / Playwright not ready**: `server.cjs` Chrome'a bağlanamıyor.
    *   **504 Gateway Timeout**: İstek işleme süresi `RESPONSE_COMPLETION_TIMEOUT`'u aştı. AI Studio yavaş yanıt veriyor veya takılmış olabilir.
    *   **502 Bad Gateway / AI Studio Error**: `server.cjs` AI Studio sayfasında bir hata mesajı (`toast` mesajı) algıladı veya AI'nın yanıtını doğru şekilde ayrıştıramadı. `errors/` anlık görüntülerini kontrol edin.
    *   **500 Internal Server Error**: `server.cjs`'de yakalanmamış bir hata oluştu. Sunucu günlüklerini ve `errors/` anlık görüntülerini kontrol edin.
*   **AI yanıtı eksik, yanlış biçimlendirilmiş veya `<<<START_RESPONSE>>>` işaretçisini içeriyor**:
    *   AI Studio'nun Web Arayüzü çıktısı kararsız. Sunucu ayrıştırmak için elinden geleni yapar, ancak başarısız olabilir.
    *   Akışsız istekler: Dönen JSON'da `response` alanı eksikse veya ayrıştırılamıyorsa, sunucu boş içerik veya ham JSON dizesi döndürebilir. AI Studio sayfasının gerçek çıktısını onaylamak için `errors/` anlık görüntülerini kontrol edin.
    *   Akışlı istekler: AI beklendiği gibi Markdown kod bloğu veya başlangıç ​​işaretçisi çıktısı vermezse, akış erken kesilebilir veya beklenmedik içerik içerebilir.
    *   İstemi ayarlamayı veya daha sonra yeniden denemeyi deneyin.
*   **Bağlamı otomatik temizleme başarısız**:
    *   Sunucu günlüğünde "Sohbet geçmişi temizlenirken veya doğrulanırken hata oluştu" veya "Doğrulama zaman aşımı" uyarısı görünüyor.
    *   **Neden**: AI Studio web sayfası güncellemesi, `server.cjs`'deki `CLEAR_CHAT_BUTTON_SELECTOR` veya `CLEAR_CHAT_CONFIRM_BUTTON_SELECTOR`'ın geçersiz olmasına neden oldu.
    *   **Çözüm**: `errors/` anlık görüntülerini kontrol edin, gerçek sayfa öğelerini kontrol etmek için tarayıcı geliştirici araçlarını kullanın ve `server.cjs` dosyasının üstündeki seçici sabitlerini güncelleyin.
    *   **Neden**: Temizleme işleminin kendisi `CLEAR_CHAT_VERIFY_TIMEOUT_MS`'den daha uzun sürdü.
    *   **Çözüm**: Ağ veya makine yavaşsa, `server.cjs`'de bu zaman aşımı süresini uygun şekilde artırmayı deneyebilirsiniz.