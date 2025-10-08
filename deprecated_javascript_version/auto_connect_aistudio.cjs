
#!/usr/bin/env node

// auto_connect_aistudio.js (v2.9 - Geliştirilmiş Başlatma ve Sayfa Yönetimi + Güzelleştirilmiş Çıktı)

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const readline = require('readline');

// --- Yapılandırma ---
const DEBUGGING_PORT = 8848;
const TARGET_URL = 'https://aistudio.google.com/prompts/new_chat'; // Hedef sayfa
const SERVER_SCRIPT_FILENAME = 'server.cjs'; // Düzeltilmiş betik adı
const CONNECTION_RETRIES = 5;
const RETRY_DELAY_MS = 4000;
const CONNECT_TIMEOUT_MS = 20000; // CDP'ye bağlanma zaman aşımı
const NAVIGATION_TIMEOUT_MS = 35000; // Sayfa gezinmesi için artırılmış zaman aşımı
const CDP_ADDRESS = `http://127.0.0.1:${DEBUGGING_PORT}`;

// --- ANSI Renkleri ---
const RESET = '\x1b[0m';
const BRIGHT = '\x1b[1m';
const DIM = '\x1b[2m';
const RED = '\x1b[31m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const BLUE = '\x1b[34m';
const MAGENTA = '\x1b[35m';
const CYAN = '\x1b[36m';

// --- Global Değişkenler ---
const SERVER_SCRIPT_PATH = path.join(__dirname, SERVER_SCRIPT_FILENAME);
let playwright; // checkDependencies içinde yüklendi

// --- Platforma Özgü Chrome Yolu ---
function getChromePath() {
    switch (process.platform) {
        case 'darwin':
            return '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
        case 'win32':
            // Program Files ve Program Files (x86) deneniyor
            const winPaths = [
                path.join(process.env.ProgramFiles || '', 'Google\\Chrome\\Application\\chrome.exe'),
                path.join(process.env['ProgramFiles(x86)'] || '', 'Google\\Chrome\\Application\\chrome.exe')
            ];
            return winPaths.find(p => fs.existsSync(p));
        case 'linux':
            // Yaygın Linux yolları deneniyor
            const linuxPaths = [
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable',
                '/opt/google/chrome/chrome',
                // Gerekirse Flatpak kurulumu için yol ekle
                // '/var/lib/flatpak/exports/bin/com.google.Chrome'
            ];
            return linuxPaths.find(p => fs.existsSync(p));
        default:
            return null; // Desteklenmeyen platform
    }
}

const chromeExecutablePath = getChromePath();

// --- Bağlantı Noktası Kontrol Fonksiyonu ---
function isPortInUse(port) {
    const platform = process.platform;
    let command;
    // console.log(`${DIM}   Bağlantı noktası ${port} kontrol ediliyor...${RESET}`); // İsteğe bağlı: Ayrıntılı kontrol
    try {
        if (platform === 'win32') {
            // Windows'ta, dinleme durumundaki TCP bağlantı noktalarını bul
            command = `netstat -ano | findstr LISTENING | findstr :${port}`;
            execSync(command); // Bulunursa hata vermez
            return true;
        } else if (platform === 'darwin' || platform === 'linux') {
            // macOS veya Linux'ta, bu bağlantı noktasını dinleyen işlemi bul
            command = `lsof -i tcp:${port} -sTCP:LISTEN`;
            execSync(command); // Bulunursa hata vermez
            return true;
        }
    } catch (error) {
        // Komut başarısız olursa (genellikle eşleşen işlem bulunamadığı anlamına gelir), bağlantı noktası kullanımda değildir
        // console.log(`Bağlantı noktası ${port} kontrol komutu başarısız oldu veya işlem bulunamadı:`, error.message.split('\n')[0]); // İsteğe bağlı hata ayıklama bilgisi
        return false;
    }
    // Desteklenmeyen platformlar için, bağlantı noktasının kullanımda olmadığını varsay
    return false;
}

// --- Bağlantı Noktasını Kullanan PID'yi Bulma --- (Yeni)
function findPidsUsingPort(port) {
    const platform = process.platform;
    const pids = [];
    let command;
    try {
        console.log(`${DIM}   Bağlantı noktası ${port}'u kullanan işlem aranıyor...${RESET}`);
        if (platform === 'win32') {
            command = `netstat -ano | findstr LISTENING | findstr :${port}`;
            const output = execSync(command).toString();
            const lines = output.trim().split('\n');
            for (const line of lines) {
                const parts = line.trim().split(/\s+/);
                const pid = parts[parts.length - 1]; // PID son sütundur
                if (pid && !isNaN(pid)) {
                    pids.push(pid);
                }
            }
        } else { // macOS or Linux
            command = `lsof -t -i tcp:${port} -sTCP:LISTEN`;
            const output = execSync(command).toString();
            const lines = output.trim().split('\n');
            for (const line of lines) {
                const pid = line.trim();
                if (pid && !isNaN(pid)) {
                    pids.push(pid);
                }
            }
        }
        if (pids.length > 0) {
             console.log(`   ${YELLOW}Bağlantı noktası ${port}'u kullanan PID bulundu: ${pids.join(', ')}${RESET}`);
        } else {
             console.log(`   ${GREEN}Bağlantı noktası ${port}'u açıkça dinleyen bir işlem bulunamadı.${RESET}`);
        }
    } catch (error) {
        // Komutun başarısız olması genellikle işlem bulunamadığı anlamına gelir
        console.log(`   ${GREEN}Bağlantı noktası ${port} için işlem arama komutu başarısız oldu veya sonuç vermedi.${RESET}`);
    }
    return [...new Set(pids)]; // Tekrarları kaldırılmış PID listesini döndür
}

// --- İşlemi Sonlandırma --- (Yeni)
function killProcesses(pids) {
    if (pids.length === 0) return true; // Sonlandırılacak işlem yok

    const platform = process.platform;
    let success = true;
    console.log(`${YELLOW}   PID sonlandırılmaya çalışılıyor: ${pids.join(', ')}...${RESET}`);

    for (const pid of pids) {
        try {
            if (platform === 'win32') {
                execSync(`taskkill /F /PID ${pid}`);
                console.log(`   ${GREEN}✅ PID ${pid} başarıyla sonlandırıldı (Windows)${RESET}`);
            } else { // macOS or Linux
                execSync(`kill -9 ${pid}`);
                console.log(`   ${GREEN}✅ PID ${pid} başarıyla sonlandırıldı (macOS/Linux)${RESET}`);
            }
        } catch (error) {
            console.warn(`   ${RED}⚠️ PID ${pid} sonlandırılırken hata oluştu: ${error.message.split('\n')[0]}${RESET}`);
            // Olası nedenler: işlem artık mevcut değil, yetersiz izinler vb.
            success = false; // En az birinin başarısız olduğunu işaretle
        }
    }
    return success;
}

// --- Readline Arayüzü Oluşturma ---
function askQuestion(query) {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
    });

    return new Promise(resolve => rl.question(query, ans => {
        rl.close();
        resolve(ans);
    }))
}

// --- Adım 1: Playwright Bağımlılıklarını Kontrol Etme ---
async function checkDependencies() {
    console.log(`${CYAN}-------------------------------------------------${RESET}`);
    console.log(`${CYAN}--- Adım 1: Bağımlılıkları Kontrol Etme ---${RESET}`);
    console.log('Aşağıdaki modüllerin kurulu olup olmadığı kontrol edilecek:');
    const requiredModules = ['express', 'playwright', '@playwright/test', 'cors'];
    const missingModules = [];
    let allFound = true;

    for (const moduleName of requiredModules) {
        process.stdout.write(`   - ${moduleName} ... `);
        try {
            require.resolve(moduleName); // Varlığını kontrol etmek için require.resolve kullan, yüklemeden
            console.log(`${GREEN}✓ Bulundu${RESET}`); // Yeşil onay işareti
        } catch (error) {
            if (error.code === 'MODULE_NOT_FOUND') {
                console.log(`${RED}❌ Bulunamadı${RESET}`); // Kırmızı X
                missingModules.push(moduleName);
                allFound = false;
            } else {
                console.log(`${RED}❌ Kontrol sırasında hata: ${error.message}${RESET}`);
                allFound = false;
                // Consider exiting if it's not MODULE_NOT_FOUND?
                // return false;
            }
        }
    }

    process.stdout.write(`   - Sunucu betiği (${SERVER_SCRIPT_FILENAME}) ... `);
    if (!fs.existsSync(SERVER_SCRIPT_PATH)) {
        console.log(`${RED}❌ Bulunamadı${RESET}`); // Kırmızı X
        console.error(`     ${RED}Hata: '${SERVER_SCRIPT_FILENAME}' dosyası beklenen yolda bulunamadı.${RESET}`);
        console.error(`     Beklenen yol: ${SERVER_SCRIPT_PATH}`);
        console.error(`     Lütfen '${SERVER_SCRIPT_FILENAME}' dosyasının bu betikle aynı dizinde olduğundan emin olun.`);
        allFound = false;
    } else {
        console.log(`${GREEN}✓ Bulundu${RESET}`); // Yeşil onay işareti
    }

    if (!allFound) {
        console.log(`\n${RED}-------------------------------------------------${RESET}`);
        console.error(`${RED}❌ Hata: Bağımlılık kontrolü başarısız!${RESET}`);
        if (missingModules.length > 0) {
            console.error(`   ${RED}Aşağıdaki Node.js modülleri eksik: ${missingModules.join(', ')}${RESET}`);
            console.log('   Lütfen kullandığınız paket yöneticisine göre bağımlılıkları yüklemek için aşağıdaki komutu çalıştırın:');
            console.log(`      ${MAGENTA}npm install ${missingModules.join(' ')}${RESET}`);
            console.log('      veya');
            console.log(`      ${MAGENTA}yarn add ${missingModules.join(' ')}${RESET}`);
            console.log('      veya');
            console.log(`      ${MAGENTA}pnpm install ${missingModules.join(' ')}${RESET}`);
            console.log('   (Eğer kuruluysa ancak hala bulunamadı hatası alıyorsanız, node_modules dizinini ve package-lock.json/yarn.lock dosyasını silip yeniden yüklemeyi deneyin)');
        }
        if (!fs.existsSync(SERVER_SCRIPT_PATH)) {
             console.error(`   ${RED}Gerekli sunucu betik dosyası eksik: ${SERVER_SCRIPT_FILENAME}${RESET}`);
             console.error(`   Lütfen auto_connect_aistudio.cjs ile aynı klasörde olduğundan emin olun.`);
        }
        console.log(`${RED}-------------------------------------------------${RESET}`);
        return false;
    }

    console.log(`\n${GREEN}✅ Tüm bağımlılık kontrolleri başarılı.${RESET}`);
    playwright = require('playwright'); // Playwright'ı sadece kontrollerden sonra yükle
    return true;
}

// --- Adım 2: Chrome'u Kontrol Etme ve Başlatma ---
async function launchChrome() {
    console.log(`${CYAN}-------------------------------------------------${RESET}`);
    console.log(`${CYAN}--- Adım 2: Chrome'u Başlatma veya Bağlanma (Hata Ayıklama Bağlantı Noktası ${DEBUGGING_PORT}) ---${RESET}`);

    // Önce bağlantı noktasının kullanımda olup olmadığını kontrol et
    if (isPortInUse(DEBUGGING_PORT)) {
        console.log(`${YELLOW}⚠️ Uyarı: Bağlantı noktası ${DEBUGGING_PORT} zaten kullanılıyor.${RESET}`);
        console.log('   Bu genellikle zaten bu bağlantı noktasını dinleyen bir Chrome örneği olduğu anlamına gelir.');
        const question = `İşlem seçin: [E/h]
  ${GREEN}E (Varsayılan): Mevcut Chrome örneğine bağlanmayı ve API sunucusunu başlatmayı dene.${RESET}
  ${YELLOW}h:        Bağlantı noktası ${DEBUGGING_PORT}'u kullanan işlemi otomatik olarak zorla sonlandır, ardından yeni bir Chrome örneği başlat.${RESET}
Lütfen bir seçenek girin [E/h]: `;
        const answer = await askQuestion(question);

        if (answer.toLowerCase() === 'h') {
            console.log(`\nTamam, yeni bir örnek başlatmayı seçtiniz. Bağlantı noktası otomatik olarak temizlenmeye çalışılacak...`);
            const pids = findPidsUsingPort(DEBUGGING_PORT);
            if (pids.length > 0) {
                const killSuccess = killProcesses(pids);
                if (killSuccess) {
                    console.log(`   ${GREEN}✅ İşlemi sonlandırma denemesi tamamlandı. Bağlantı noktasını kontrol etmek için 1 saniye bekleniyor...${RESET}`);
                    await new Promise(resolve => setTimeout(resolve, 1000)); // Kısa bekleme
                    if (isPortInUse(DEBUGGING_PORT)) {
                        console.error(`${RED}❌ Hata: Sonlandırma denemesinden sonra, bağlantı noktası ${DEBUGGING_PORT} hala kullanılıyor.${RESET}`);
                        console.error('   Olası nedenler: Yetersiz izinler veya işlem düzgün sonlandırılamadı. Lütfen işlemi manuel olarak sonlandırmayı deneyin.' );
                         // Manuel temizleme ipucu ver
                         console.log(`${YELLOW}İpucu: İşlem kimliğini (PID) bulmak için aşağıdaki komutları kullanabilirsiniz:${RESET}`);
                         if (process.platform === 'win32') {
                             console.log(`  - CMD veya PowerShell'de: netstat -ano | findstr :${DEBUGGING_PORT}`);
                             console.log('  - PID'yi bulduktan sonra şunu kullanın: taskkill /F /PID <PID>');
                         } else { // macOS or Linux
                             console.log(`  - Terminalde: lsof -t -i:${DEBUGGING_PORT}`);
                             console.log('  - PID'yi bulduktan sonra şunu kullanın: kill -9 <PID>');
                         }
                         await askQuestion('Lütfen işlemi manuel olarak sonlandırdıktan sonra betiği yeniden denemek için Enter tuşuna basın...');
                         process.exit(1); // Çık, kullanıcının halletmesine ve yeniden çalıştırmasına izin ver
                    } else {
                        console.log(`   ${GREEN}✅ Bağlantı noktası ${DEBUGGING_PORT} şimdi boşta.${RESET}`);
                        // Bağlantı noktası temizlendi, aşağıdaki Chrome başlatma işlemine devam et
                    }
                } else {
                    console.error(`${RED}❌ Hata: Bağlantı noktasını kullanan işlemlerin bir kısmını veya tamamını sonlandırma denemesi başarısız oldu.${RESET}`);
                    console.error('   Lütfen günlüklerdeki belirli hata mesajlarını kontrol edin, işlemi manuel olarak sonlandırmanız gerekebilir.');
                    await askQuestion('Lütfen işlemi manuel olarak sonlandırdıktan sonra betiği yeniden denemek için Enter tuşuna basın...');
                    process.exit(1); // Çık, kullanıcının halletmesine ve yeniden çalıştırmasına izin ver
                }
            } else {
                console.log(`${YELLOW}   Bağlantı noktası kullanımda olmasına rağmen, dinleyen belirli bir işlem PID'si bulunamadı. Durum karmaşık olabilir, manuel kontrol önerilir.${RESET}` );
                 await askQuestion('Lütfen manuel olarak kontrol edip bağlantı noktasının boş olduğundan emin olduktan sonra betiği yeniden denemek için Enter tuşuna basın...');
                 process.exit(1); // Çık
            }
            // Kod buraya ulaşırsa, bağlantı noktası temizliğinin başarılı olduğu ve Chrome'u başlatmaya devam edeceği anlamına gelir
            console.log(`\nYeni bir Chrome örneği başlatmaya hazırlanılıyor...`);

        } else {
            console.log(`\nTamam, mevcut Chrome örneğine bağlanılmaya çalışılacak...`);
            return 'use_existing'; // Ana sürece başlatmayı atlamasını ve doğrudan bağlanmasını söyleyen özel dönüş değeri
        }
    }

    // --- Bağlantı noktası kullanımda değilse veya kullanıcı 'h' seçip otomatik temizleme başarılı olursa ---

    if (!chromeExecutablePath) {
        console.error(`${RED}❌ Hata: Mevcut işletim sisteminde (${process.platform}) yaygın yollarda Chrome yürütülebilir dosyası bulunamadı.${RESET}`);
        console.error('   Lütfen Google Chrome'un kurulu olduğundan emin olun veya betikteki getChromePath işlevini doğru yolu gösterecek şekilde değiştirin.');
        if (process.platform === 'win32') {
             console.error('   (%ProgramFiles% ve %ProgramFiles(x86)% altındaki yollar denendi)');
        } else if (process.platform === 'linux') {
             console.error('   (/usr/bin/google-chrome, /usr/bin/google-chrome-stable, /opt/google/chrome/chrome yolları denendi)');
        }
        return false;
    }

    console.log(`   ${GREEN}Chrome yolu bulundu:${RESET} ${chromeExecutablePath}`);

    // Yalnızca açıkça yeni bir örnek başlatılması gerektiğinde diğer örnekleri kapatmayı iste
    // (Yukarıda 'h' seçilip temizleme başarılı olduysa, isPortInUse burada false döndürmelidir)
    if (!isPortInUse(DEBUGGING_PORT)) {
         console.log(`${YELLOW}⚠️ Önemli Not: Yeni hata ayıklama bağlantı noktasının etkili olmasını sağlamak için, önce müdahale edebilecek *diğer* tüm Google Chrome örneklerinden manuel olarak tamamen çıkmanız önerilir.${RESET}`);
         console.log('   (macOS'ta genellikle Cmd+Q, Windows/Linux'ta tüm pencereleri kapat)');
         await askQuestion('Lütfen diğer Chrome örneklerini hallettiğinizi onaylayın, ardından başlatmaya devam etmek için Enter tuşuna basın...');
    } else {
         // Teorik olarak buraya gelmemeli, çünkü bağlantı noktası temizlendi veya use_existing seçildi
         console.warn(`   ${YELLOW}Uyarı: Bağlantı noktası ${DEBUGGING_PORT} beklenmedik bir şekilde hala kullanılıyor. Başlatmaya devam edilecek, ancak bu büyük olasılıkla başarısız olacaktır.${RESET}`);
         await askQuestion('Lütfen başlatmayı denemeye devam etmek için Enter tuşuna basın...');
    }


    console.log(`Chrome başlatılmaya çalışılıyor...`);
    console.log(`  Yol: "${chromeExecutablePath}"`);
    // --- Değişiklik: Başlatma parametreleri ekle ---
    const chromeArgs = [
        `--remote-debugging-port=${DEBUGGING_PORT}`,
        `--window-size=460,800` // Genişliği 460 piksel olarak belirt, yükseklik geçici olarak 800 piksel (gerektiğinde ayarlanabilir)
        // Buraya diğer gerekli Chrome başlatma parametrelerini ekleyebilirsiniz
    ];
    console.log(`  Parametreler: ${chromeArgs.join(' ')}`); // Tüm parametreleri yazdır

    try {
        const chromeProcess = spawn(
            chromeExecutablePath,
            chromeArgs, // Pencere boyutunu içeren parametre dizisini kullan
            { detached: true, stdio: 'ignore' } // Gerekirse betiğin bağımsız olarak çıkmasına izin vermek için ayır
        );
        chromeProcess.unref(); // Ana işlemin bağımsız olarak çıkmasına izin ver

        console.log(`${GREEN}✅ Chrome başlatma komutu gönderildi (belirtilen pencere boyutuyla). Daha sonra bağlanılmaya çalışılacak...${RESET}`);
        console.log(`${DIM}⏳ Chrome işleminin başlaması için 3 saniye bekleniyor...${RESET}`);
        await new Promise(resolve => setTimeout(resolve, 3000));
        return true; // Başlatma işleminin denendiğini belirtir

    } catch (error) {
        console.error(`${RED}❌ Chrome başlatılırken hata oluştu: ${error.message}${RESET}`);
        console.error(`   Lütfen "${chromeExecutablePath}" yolunun doğru olup olmadığını ve yürütme izniniz olup olmadığını kontrol edin.`);
        return false;
    }
}

// --- Adım 3: Playwright'a Bağlanma ve Sayfayı Yönetme (Yeniden Denemeli) ---
async function connectAndManagePage() {
    console.log(`${CYAN}-------------------------------------------------${RESET}`);
    console.log(`${CYAN}--- Adım 3: Playwright'ı ${CDP_ADDRESS} adresine bağlama (en fazla ${CONNECTION_RETRIES} deneme) ---${RESET}`);
    let browser = null;
    let context = null;

    for (let i = 0; i < CONNECTION_RETRIES; i++) {
        try {
            console.log(`\n${DIM}Playwright'a bağlanmaya çalışılıyor (${i + 1}/${CONNECTION_RETRIES}. deneme)...${RESET}`);
            browser = await playwright.chromium.connectOverCDP(CDP_ADDRESS, { timeout: CONNECT_TIMEOUT_MS });
            console.log(`${GREEN}✅ Chrome'a başarıyla bağlandı!${RESET}`);

             // Basitleştirilmiş bağlam alma
             await new Promise(resolve => setTimeout(resolve, 500)); // Bağlandıktan sonra kısa gecikme
             const contexts = browser.contexts();
             if (contexts && contexts.length > 0) {
                 context = contexts[0];
                 console.log(`-> Tarayıcı varsayılan bağlamı alındı.`);
                 break; // Bağlantı ve bağlam başarılı
             } else {
                 // Bu durum, connectOverCDP duyarlı bir Chrome ile başarılı olursa nadir olmalıdır
                 throw new Error('Bağlantı başarılı, ancak tarayıcı bağlamı alınamıyor. Chrome yanıt vermiyor veya tam olarak başlatılmamış olabilir.');
             }

        } catch (error) {
            console.warn(`   ${YELLOW}Bağlantı denemesi ${i + 1} başarısız: ${error.message.split('\n')[0]}${RESET}`);
             if (browser && browser.isConnected()) {
                 // connectOverCDP başarısız olursa olmamalı, ama iyi bir uygulama
                 await browser.close().catch(e => console.error("Bağlantısı başarısız olan tarayıcıyı kapatmaya çalışırken hata:", e));
             }
             browser = null;
             context = null;

            if (i < CONNECTION_RETRIES - 1) {
                console.log(`   ${YELLOW}Olası nedenler: Chrome tam olarak başlatılmadı / Bağlantı noktası ${DEBUGGING_PORT} dinlenmiyor / Bağlantı noktası meşgul.${RESET}`);
                console.log(`${DIM}   ${RETRY_DELAY_MS / 1000} saniye sonra yeniden denenecek...${RESET}`);
                await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS));
            } else {
                console.error(`\n${RED}❌ ${CONNECTION_RETRIES} denemeden sonra hala bağlanılamıyor.${RESET}`);
                console.error('   Lütfen tekrar kontrol edin:');
                console.error('   1. Chrome'un betik tarafından gerçekten başarıyla başlatılıp başlatılmadığını ve pencerenin görünür ve yüklenmiş olup olmadığını? (Google'da oturum açmanız gerekebilir)');
                console.error(`   2. Başka bir programın ${DEBUGGING_PORT} bağlantı noktasını kullanıp kullanmadığını? (Kontrol komutu: macOS/Linux: lsof -i :${DEBUGGING_PORT} | Windows: netstat -