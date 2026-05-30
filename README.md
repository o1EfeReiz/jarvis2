# J.A.R.V.I.S PyQt Uygulaması

Bu sürüm, verdiğin `main.py`, `wake.py` ve `assistant.py` mantığını tek bir PyQt6 arayüzünde birleştirir.

## Kurulum

```powershell
pip install -r requirements.txt
copy .env.example .env
```

`.env` dosyasına OpenAI API anahtarını ekle:

```env
OPENAI_API_KEY=...
```

## Çalıştırma

```powershell
python jarvis_app.py
```

## Kullanım

- Yazılı komut için alttaki komut kutusunu kullan.
- `MIKROFON` tek seferlik sesli komut dinler.
- `WAKE` arka planda wake-word dinlemeyi açar.
- Pencere sürüklenebilir, çerçevesizdir ve ekranın sağ altında küçük bir panel olarak üstte kalır.
- Üstteki `-`, `□`, `×` butonları sırasıyla alta alır, paneli büyütür/küçültür ve kapatır.
- `kendi sesini %50 ye al` gibi komutlarla JARVIS'in kendi konuşma sesini ayarlayabilirsin.

## Windows Açılınca Otomatik Başlatma

Bir kez şunu çalıştır:

```powershell
.\enable_startup.bat
```

Bu kayıt JARVIS'i Windows açılınca sol üst köşede küçük çizgi modu ile başlatır.
Çizgiye çift tıklayınca normal panele döner.

Otomatik başlatmayı kapatmak için:

```powershell
.\disable_startup.bat
```

## Wake Word Modeli Eksikse

`WAKE` butonuna basınca model eksik uyarısı görürsen şu komutu dene:

```powershell
.\download_wake_models.bat
```

Bu olmazsa `MIKROFON` butonu yine normal şekilde tek seferlik sesli komut alır.

## Güvenli Komutlar

Bilgisayarı kapatma, yeniden başlatma ve LoL otomatik seçim gibi riskli işlemler önce onay ister. Onaylamak için `bunu yap` komutunu ver.

## Virus Taramasi

JARVIS Windows Defender uzerinden temel kontrol yapabilir:

```text
bilgisayarimda virus var mi kontrol et
hizli virus taramasi yap
tam virus taramasi yap
windows guvenligi ac
```

Tam tarama uzun surebilecegi icin once onay ister.

## Zamanli Kapatma

```text
15 dakika sonra bilgisayari kapat
kapanmaya son 30 saniye kala bana secenek sun
onayla
iptal et
```

JARVIS zamanli kapatmayi Windows'a kurar. Son 30 saniye kala iptal etmek icin sesli veya yazili `iptal et` demen yeterli.

## LoL Yardim Modu

Bu mod hesap riski olan otomatik kabul / otomatik kilitleme yapmaz. Rün ve build sayfalarini acar, sampiyon/rol hazirligini hatirlar.

```text
lol yardim modu
favori sampiyon kaydet yasuo mid
yasuo mid hazirla
zed runlerini ac
viego jungle build ac
lol modu kapat
```

JARVIS U.GG, OP.GG ve LoLalytics aramalarini acar; kabul, pick ve kilitleme adimlarini manuel yapmalisin.

## Kick / Opera

```text
operadan kick i ac elwind yayinda mi bak
operadan kick i ac elwind yayindaysa yayini tam ekran ac yan ekrana koy
kick.com a giris yap
```

JARVIS Kick kanalini Opera'da acar. Yayinda bilgisi okunabilirse soyler; tam ekran ve yan ekrana tasima icin Windows kisayollarini dener.

## Ceviri

```text
siteyi turkceye cevir
sayfayi turkce yap
secili yaziyi turkceye cevir
ekrandaki sayfayi turkceye cevir
```

Site cevirisinde aktif sekmenin adresi kopyalanir ve Google Translate'in web sitesi ceviri modu acilir. Secili yazi cevirisinde once yaziyi secmen gerekir.

## Riot Guvenli Modu

Riot Client, League of Legends veya Valorant acilinca JARVIS otomatik olarak mini moda iner, wake dinlemeyi durdurur ve sessiz moda gecer. Riot/oyun surecleri kapaninca paneli geri getirir ve wake'i tekrar baslatir.

## Cockpit / Ikinci Ekran Modu

Buyuk yan ekran panelini baslatmak icin:

```powershell
.\run_jarvis_cockpit.bat
```

Windows acilinca direkt cockpit modu ile baslamasini istersen:

```powershell
.\enable_startup_cockpit.bat
```

Uygulama icindeyken su komutlari kullanabilirsin:

```text
kokpit ac
yan ekran modu
paneli buyut
kokpit kapat
normal panele don
```

## JARVIS v3 Beyin

Bu surumde JARVIS artik sadece komut listesinden ibaret degil. `jarvis_brain.py`
dosyasi GPT-5.5 tabanli bir karar katmani olarak calisir:

- Once cumlenin niyetini ayirir: soru mu, sistem komutu mu, plan mi, panel mi?
- "YouTube short nasil indirilir?" gibi sorulari artik YouTube aramasi sanmaz.
- "Spotify'da su sarkiyi ac" gibi isleri temiz bir yerel komuta cevirir.
- Acikca soyledigin tercihleri `jarvis_memory.json` dosyasinda hatirlamaya baslar.
- Ozel kisi arama, riskli sistem islemleri ve mahremiyet konularinda sinir koyar.

Ana model ayari `.env` icinden gelir:

```env
OPENAI_MODEL=gpt-5.5
OPENAI_FALLBACK_MODEL=gpt-4.1-mini
JARVIS_SIMPLE_MODEL=gpt-4.1-mini
JARVIS_COMPLEX_MODEL=gpt-4o
JARVIS_SIMPLE_MAX_TOKENS=300
JARVIS_COMPLEX_MAX_TOKENS=1000
JARVIS_SIMPLE_TEMPERATURE=0.7
JARVIS_COMPLEX_TEMPERATURE=0.5
OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
OPENAI_VISION_MODEL=gpt-5.5
OPENAI_RESEARCH_MODEL=gpt-5.5
SCREEN_WATCH_INTERVAL_SECONDS=30
JARVIS_VOICE=tr-TR-EmelNeural
VOICE_RATE=+20%
VOICE_PITCH=+5Hz
VOICE_VOLUME_PERCENT=22
WAKE_THRESHOLD=0.15
WAKE_CHUNK=1280
MIC_ENERGY_THRESHOLD=220
MIC_PAUSE_THRESHOLD=1.05
MIC_NON_SPEAKING_DURATION=0.45
MIC_AMBIENT_DURATION=0.7
```

JARVIS'i daha zeki yapmak icin bundan sonraki buyuk adim, bu v3 karar katmanina
ekran okuma, tarayici kontrolu, takvim ve dosya araclarini guvenli izin sistemiyle
baglamaktir.

Cevap uretimi iki katmanlidir: basit/kisa sorular `gpt-4.1-mini`, karmasik
analiz ve strateji sorulari `gpt-4o` ile yanitlanir. Yerel komutlarda cevap
modeli cagrilmaz; komut dogrudan calisir.

Kullanabilecegin v3 komutlari:

```text
v3 durum
v3 kapat
v3 ac
bunu hatirla: toplantilari sabah planlamak istiyorum
neleri hatirliyorsun
hafizayi temizle
```

## Canli Ekran Modu

Bu mod acik izinle calisir. Komutu verdiginde JARVIS once onay ister; `bunu yap`
dedikten sonra belirlenen sure boyunca ekrani belirli araliklarla yorumlar. Ekran
goruntuleri dosyaya kaydedilmez, anlik analiz icin bellekte kullanilir.

```text
ekranima 10 dakika bak
canli ekran modunu ac
ekran izlemeyi durdur
```

Ekran modunda `pyscreeze/Pillow` hatasi gorursen su komutu bir kez calistir:

```powershell
.\.venv\Scripts\python.exe -m pip install pillow pyscreeze
```

Yeni kodda JARVIS once PyAutoGUI ile ekran goruntusu alir; bu calismazsa PyQt
ekran yakalama yedegine duser.

## Web Arastirma Modu

Kaynakli ve guncel bilgi isteyen sorular icin Responses API web search araci
kullanilir. JARVIS cevapta kaynaklari ve tarihi belirtmeye calisir; arama
calismazsa tahmin uydurmaz.

```text
roblox kodlarini resmi sayfadan kontrol et
bu uygulamanin guncel surumunu webden arastir
wiki den ve resmi sayfadan karsilastir
```

## Geri Bildirimle Ogrenme

JARVIS cevap stilini ve yanlis anlama durumlarini hafizaya kural olarak kaydeder.

```text
bu cevap iyiydi
cok uzun cevap verdin
beni yanlis anladin
kisa cevap ver
bunu ders olarak al: oyun oynarken once kisa taktik ver
komut ogrenme raporu
```

## Teshis ve Yonetici Komutlari

JARVIS artik son komutlarin sonucunu, hatalari ve kullanicidan gelen dersleri
hafizaya kaydeder. Sistem durumu ve kendi sagligi icin kisa teshis verebilir.

```text
kendini kontrol et
jarvis teshis yap
son hatalarin ne
guvenlik kurallarin ne
hafizadan oyun sil
```

## Oyun Modu CSGO

```text
oyun modu csgo
oyun modu csgo onayliyorum
```

Bu mod Discord ve Steam'i korur; Chrome, Edge, Opera, Firefox, Spotify ve bazi
oyun launcherlarini kapatmayi dener. Ardindan Counter-Strike'i Steam AppID 730
uzerinden baslatir. Kaydedilmemis dosya riski olan editorleri zorla kapatmaz.

## Riot Oyun Modlari

```text
oyun modu lol
oyun modu valorant
oyun modundan cik
```

LOL ve Valorant modlari Riot/Vanguard processlerine dokunmaz. Chrome, Opera,
Edge, Firefox, Roblox, Steam, Epic Games, VS Code ve Codex gibi dikkat dagitan
processleri kapatmayi dener. Valorant modunda Spotify da kapatilir; LOL modunda
Spotify yeniden baslatilir. Mod aktifken JARVIS sadece ses yukselt/azalt,
Discord ac/kapat ve oyun modundan cik komutlarina cevap verir.

## Startup, Backup ve Log

Task Scheduler gorevlerini kurmak icin:

```powershell
.\install_jarvis_tasks.bat
```

Bu kurulum iki gorev ekler:

- `JarvisStartup`: kullanici oturum actiginda `run_jarvis.bat --mini --silent` calisir.
- `JarvisDailyBackup`: her gun 03:00'de `run_jarvis_backup.bat` calisir.

Backup hedefi:

```text
C:\jarvis_v2\backups\YYYY-MM-DD\
```

Yedeklenenler: `jarvis_app.py`, `jarvis_memory.json`, `jarvis_changelog.txt`,
`coords.json` ve Windows DPAPI ile sifrelenmis `.env.encrypted.txt`. Son 7 gun
tutulur, eski klasorler otomatik silinir.

Task Scheduler gorevlerini kaldirmak icin:

```powershell
.\remove_jarvis_tasks.bat
```

Calisma kayitlari `jarvis_log.txt` dosyasina yazilir: acilis/kapanis,
komutlar, kullanilan model, hatalar ve oyun modu giris/cikis olaylari.

## Dosya / PDF / Gorsel Analizi

Paneldeki `DOSYA` butonundan PDF, fotograf, ekran goruntusu, TXT/MD/CSV/JSON
veya DOCX dosyasi ekleyebilirsin. JARVIS son eklenen dosyayi hatirlar.

```text
dosya ekle
hangi dosya ekli
bu dosyayi tara ve ozetini anlat
pdf dosyasini oku ve önemli maddeleri cikar
ekli dosyayi kaldir
```

PDF okumak icin `pypdf` paketi gerekir. Eksikse:

```powershell
.\.venv\Scripts\python.exe -m pip install pypdf
```
