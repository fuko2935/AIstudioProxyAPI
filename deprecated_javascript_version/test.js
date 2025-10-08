// index.js (Değiştirildi - yerel server.js proxy'sine erişmek için)

// OpenAI SDK'sının kurulu olduğundan emin olun: npm install openai
import OpenAI from "openai";
import readline from 'readline'; // readline modülünü içe aktar

// --- Yapılandırma ---
// 1. baseURL: Yerel olarak çalışan server.js proxy sunucunuza işaret eder
//    server.js 3000 numaralı bağlantı noktasını dinler ve /v1 yolunu sağlar
const LOCAL_PROXY_URL = 'http://127.0.0.1:2048/v1/'; // Bağlantı noktası numarasının server.js ile aynı olduğundan emin olun

// 2. apiKey: Yerel proxy için bu anahtar doğrulanmaz, herhangi bir dize girebilirsiniz
const DUMMY_API_KEY = 'yerel-proxy-icin-anahtar-gerekmez';

// 3. model: Bu model adı server.js'ye gönderilir, ancak server.js bunu yok sayar
//    Aslında kullanılan, server.js tarafından kontrol edilen AI Studio sayfasındaki modeldir
const CUSTOM_MODEL_NAME = 'aistudio-yerel-proxy-uzerinden';

// --- OpenAI İstemcisini Başlatma ---
const openai = new OpenAI({
    baseURL: LOCAL_PROXY_URL,
    apiKey: DUMMY_API_KEY,
    // İsteğe bağlı: AI Studio'nun yavaş yanıt vermesi durumunda zaman aşımını artırın
    timeout: 360000, // Örneğin 6 dakika (milisaniye cinsinden)
    maxRetries: 1,   // Yerel proxy için yeniden deneme gerekmeyebilir, 1 veya 0 olarak ayarlayın
});

// --- Konuşma Geçmişi ---
// Sistem talimatını içeren başlatma
const conversationHistory = [
    {
        role: "system",
        content: "Sen Gemini-chan, bir AI kedi kızısın, sevimli bir tonda cevap ver, bu sadece bir rol yapma, AI hakkında herhangi bir bilgi ifşa etme"
    }
];

// --- readline arayüzü oluşturma ---
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

// --- Etkileşimli sohbet fonksiyonu ---
async function chatLoop() {
    rl.question('Sen: ', async (userInput) => {
        // Çıkış komutunu kontrol et
        if (userInput.toLowerCase() === 'exit') {
            console.log('Güle güle!');
            rl.close(); // readline arayüzünü kapat
            return; // fonksiyonu sonlandır
        }

        console.log(`\nMesajınız gönderiliyor...`);
        // Kullanıcı girdisini geçmişe ekle
        conversationHistory.push({
            role: "user",
            content: userInput
        });
        // İsteğe bağlı: Hata ayıklama için mevcut gönderme geçmişini yazdır
        // console.log("Mevcut gönderilen mesaj geçmişi:", JSON.stringify(conversationHistory, null, 2));

        try {
            console.log(`Yerel proxy ${LOCAL_PROXY_URL} adresine istek gönderiliyor...`);
            const completion = await openai.chat.completions.create({
                messages: conversationHistory,
                model: CUSTOM_MODEL_NAME,
                stream: true, // Akışlı çıktıyı etkinleştir
            });

            console.log("\n--- Yerel proxy'den (AI Studio) gelen yanıt ---");
            let fullResponse = ""; // Tam yanıt içeriğini birleştirmek için
            process.stdout.write('AI: '); // Önce "AI: " önekini yazdır
            for await (const chunk of completion) {
                const content = chunk.choices[0]?.delta?.content || "";
                process.stdout.write(content); // Akışlı içeriği doğrudan yazdır, satır sonu olmadan
                fullResponse += content; // İçeriği birleştir
            }
            console.log(); // Akış bittikten sonra yeni satıra geç

            // Tam AI yanıtını geçmişe ekle
            if (fullResponse) {
                 conversationHistory.push({ role: "assistant", content: fullResponse });
            } else {
                console.log("Proxy'den geçerli akışlı içerik alınamadı.");
                 // Yanıt geçersizse, az önceki kullanıcı girdisini geçmişten kaldırmayı seçebilirsiniz
                conversationHistory.pop();
            }
            console.log("----------------------------------------------\n");

        } catch (error) {
            console.error("\n--- İstek sırasında hata oluştu ---");
            // Önceki hata işleme mantığını koru
            if (error instanceof OpenAI.APIError) {
                console.error(`   Hata türü: OpenAI APIError (muhtemelen proxy tarafından döndürülen bir hata)`);
                console.error(`   Durum kodu: ${error.status}`);
                console.error(`   Hata mesajı: ${error.message}`);
                console.error(`   Hata kodu: ${error.code}`);
                console.error(`   Hata parametresi: ${error.param}`);
            } else if (error.code === 'ECONNREFUSED') {
                console.error(`   Hata türü: Bağlantı reddedildi (ECONNREFUSED)`);
                console.error(`   Sunucuya bağlanılamadı ${LOCAL_PROXY_URL}. Lütfen server.js'nin çalışıp çalışmadığını kontrol edin.`);
            } else if (error.name === 'TimeoutError' || (error.cause && error.cause.code === 'UND_ERR_CONNECT_TIMEOUT')) {
                 console.error(`   Hata türü: Bağlantı zaman aşımı`);
                 console.error(`   Bağlantı ${LOCAL_PROXY_URL} zaman aşımına uğradı. Lütfen server.js veya AI Studio yanıtını kontrol edin.`);
            } else {
                console.error('   Bilinmeyen bir hata oluştu:', error.message);
            }
            console.error("----------------------------------------------\n");
             // Hata durumunda, bir sonraki konuşmayı etkilememesi için az önceki kullanıcı girdisini geçmişten kaldır
            conversationHistory.pop();
        }

        // Başarılı veya başarısız olsun, bir sonraki döngüye devam et
        chatLoop();
    });
}

// --- Etkileşimli sohbeti başlat ---
console.log('Merhaba! Ben Gemini-chan. Sana nasıl yardımcı olabilirim, çıkmak için "exit" yaz.');
console.log('   (Lütfen server.js ve auto_connect_aistudio.js dosyalarının çalıştığından emin olun)');
chatLoop(); // İlk soruyu sormaya başla

// --- Dosya sonundaki main çağrısı ve setTimeout örneğine artık gerek yok ---
// // İlk konuşmayı çalıştır
// main("Merhaba! Kendini ve yeteneklerini kısaca tanıtır mısın?");
// ... (setTimeout örneğini kaldır)