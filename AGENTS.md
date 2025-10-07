# Depo Katkı ve Geliştirme Rehberi

Bu rehber, AI Studio Proxy API projesine katkıda bulunmak, kod yapısını anlamak ve geliştirme sürecine dahil olmak isteyenler için hazırlanmıştır.

##  Mimari Bakış

Proje, yüksek performansı ve sürdürülebilirliği sağlamak amacıyla modern ve modüler bir mimari üzerine kurulmuştur. Temel bileşenler şunlardır:

1.  **Üç Katmanlı Yanıt Alma Mekanizması**: İstekler, en hızlıdan en yavaşa doğru şu üç katman tarafından sırayla karşılanmaya çalışılır:
    *   **Stream Proxy (`stream/`)**: Entegre akış proxy'si. En yüksek performansı sunar ve varsayılan yanıtlama mekanizmasıdır.
    *   **Harici Yardımcı Servis**: İsteğe bağlı olarak yapılandırılabilen harici bir servis.
    *   **Playwright Sayfa Etkileşimi (`browser_utils/`)**: En son çare olarak, tarayıcıyı doğrudan otomatize ederek yanıtı alır. En esnek ama en yavaş yöntemdir.

2.  **Asenkron İstek Kuyruğu (`api_utils/queue_worker.py`)**: Gelen tüm API istekleri bir kuyruğa alınır ve bir "worker" tarafından sırayla işlenir. Bu, tarayıcı otomasyonu gibi tek seferde yalnızca bir tane çalıştırılabilecek kaynaklar üzerindeki çakışmaları önler ve sistemi stabil tutar.

3.  **Birleşik Yapılandırma (`.env` ve `config/`)**: Tüm ayarlar `.env` dosyası üzerinden yönetilir ve `config/` modülü aracılığıyla uygulamaya dağıtılır. Bu, geliştirme, test ve dağıtım ortamları arasında kolayca geçiş yapmayı sağlar.

## Proje Yapısı ve Modül Organizasyonu

Proje, sorumlulukları net bir şekilde ayıran modüler bir yapıya sahiptir:

-   `api_utils/`: FastAPI uygulamasının kalbidir.
    -   `app.py`: Uygulama yaşam döngüsü (başlatma/kapatma), ara katmanlar (middleware) ve global durumların yönetimini içerir.
    -   `routes.py`: Tüm API endpoint'lerinin (örn: `/v1/chat/completions`) tanımlandığı yerdir.
    -   `request_processor.py`: Bir isteğin baştan sona nasıl işleneceğinin (model değiştirme, parametre ayarlama, yanıt alma vb.) mantığını barındırır.
    -   `queue_worker.py`: Arka planda çalışarak istek kuyruğunu yöneten asenkron "worker".
    -   `auth_utils.py`: API anahtar doğrulama mantığını içerir.
-   `browser_utils/`: Tarayıcı otomasyonu ile ilgili tüm işlemleri yönetir.
    -   `page_controller.py`: Tarayıcı sayfasının yaşam döngüsünü, gezinmeyi ve durum takibini yönetir.
    -   `model_management.py`: AI Studio (Qwen) arayüzündeki model listesini okuma ve model değiştirme gibi işlemleri yapar.
    -   `script_manager.py`: Dinamik olarak "userscript" (örneğin, daha fazla model ekleyen) enjekte etme işlevini yönetir.
-   `config/`: Projenin tüm yapılandırma ayarlarını merkezileştirir.
    -   `settings.py`: `.env` dosyasından ortam değişkenlerini okur.
    -   `constants.py`: Sabit değerleri (örn: varsayılan model adları) tanımlar.
    -   `selectors.py`: Playwright'in sayfa elemanlarını bulmak için kullandığı CSS seçicilerini barındırır.
-   `models/`: Pydantic veri modellerini içerir. API istek ve yanıtlarının yapısını tanımlar.
-   `stream/`: Yüksek performanslı entegre akış (streaming) proxy sunucusunun kodlarını barındırır.
-   `tests/`: `pytest` testlerinin bulunduğu dizin.
-   **Kök Dizin**: `launch_camoufox.py` (ana başlatıcı), `server.py` (FastAPI app nesnesini barındırır) ve `gui_launcher.py` (grafik arayüz) gibi temel betikleri içerir.

## Geliştirme Ortamı Kurulumu ve Komutlar

Proje, bağımlılık yönetimi için **Poetry** kullanmaktadır.

1.  **Bağımlılıkları Yükle**: Proje kök dizininde `poetry install --with dev` komutunu çalıştırarak hem üretim hem de geliştirme bağımlılıklarını kurun.
2.  **Sanal Ortamı Aktifleştir**: `poetry shell` komutuyla Poetry'nin oluşturduğu sanal ortama giriş yapın.
3.  **Tarayıcı ve Bağımlılıklarını Kur**:
    -   `camoufox fetch`: Anti-fingerprinting tarayıcısını indirir.
    -   `playwright install-deps firefox`: Tarayıcının çalışması için gerekli sistem kütüphanelerini kurar.
4.  **Geliştirme Sunucusunu Başlat**:
    -   `poetry run python launch_camoufox.py --debug`: Tarayıcı arayüzünü görerek hata ayıklama modunda başlatır. İlk kimlik doğrulama için bu gereklidir.
    -   `poetry run uvicorn server:app --reload --port 2048`: Kodda değişiklik yaptığınızda sunucunun otomatik olarak yeniden başlamasını sağlayan sıcak yeniden yükleme (hot-reload) modunda çalıştırır.
5.  **Testleri Çalıştır**:
    -   `poetry run pytest`: `tests/` dizinindeki tüm testleri çalıştırır.
    -   `poetry run pytest tests/test_model_catalog.py`: Sadece belirli bir test dosyasını çalıştırır.

## Kodlama Stili ve Adlandırma Kuralları

-   **Formatlama**: Kodlar, `black` formatlayıcısı ile formatlanmalı ve `isort` ile import sıralaması düzenlenmelidir. Commit atmadan önce `poetry run black .` ve `poetry run isort .` komutlarını çalıştırın.
-   **Linting**: Kod stili kontrolü için `flake8` kullanılır. `poetry run flake8 .` ile kontrol edebilirsiniz.
-   **Tip Kontrolü (Type Checking)**: Proje, statik tip ipuçlarını (type hints) kullanır ve `pyright` ile kontrol edilir. `npx pyright` komutuyla tip hatalarını denetleyebilirsiniz.
-   **Adlandırma**: Fonksiyonlar ve değişkenler için `snake_case`, sınıflar için `PascalCase` kullanılır.
-   **Docstrings**: Tüm genel (public) modüller, sınıflar ve fonksiyonlar için açıklayıcı docstring'ler yazılmalıdır. Örnek:
    ```python
    from typing import Optional

    def get_user_by_id(user_id: int) -> Optional[dict]:
        """
        Verilen ID'ye göre kullanıcıyı veritabanından getirir.

        Args:
            user_id: Aranacak kullanıcının ID'si.

        Returns:
            Kullanıcı bilgilerini içeren bir sözlük veya bulunamazsa None.
        """
        # ... fonksiyon içeriği ...
    ```

## Commit ve Pull Request Kuralları

-   **Commit Mesajları**: Lütfen [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) formatına uyun. Bu, değişikliklerinizi anlamayı ve sürüm notları oluşturmayı kolaylaştırır.
    -   `feat:`: Yeni bir özellik eklediğinizde.
    -   `fix:`: Bir hatayı düzelttiğinizde.
    -   `docs:`: Sadece dokümantasyonda değişiklik yaptığınızda.
    -   `refactor:`: Kullanıcıyı etkilemeyen kod iyileştirmeleri yaptığınızda.
    -   `chore:`: Derleme süreçleri, bağımlılık yönetimi gibi rutin işler için.
-   **Pull Request (PR) Süreci**:
    1.  Tüm testlerin geçtiğinden emin olun (`poetry run pytest`).
    2.  Kodun formatlandığından ve lint hataları olmadığından emin olun.
    3.  PR açıklamasında yaptığınız değişiklikleri net bir şekilde özetleyin.
    4.  Eğer bir arayüz değişikliği yaptıysanız ekran görüntüleri, arka plan değişikliği yaptıysanız ilgili logları ekleyin.
    5.  İlgili "issue" numarasını PR açıklamasında belirtin (örn: `Fixes #123`).