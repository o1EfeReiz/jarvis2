# jarvis-main.zip Guvenlik ve Tasima Raporu

Kaynak dosya: `C:\Users\emir1\Downloads\jarvis-main.zip`

## Kisa Sonuc

Bu ZIP'i dogrudan calistirmadim. Statik olarak actim ve inceledim.

Ilk bulgu: proje Windows icin degil, macOS icin yazilmis bir JARVIS projesi. Icindeki `Windows.txt` dosyasi da Windows surumunun henuz eklenmedigini soyluyor.

Malware gibi gizli kalicilik, kripto madenci, sifre calici veya arka kapı davranisi net olarak gorunmedi. Ama proje cok yetkili bir asistan olarak tasarlanmis:

- Mikrofon dinler.
- Gemini Live API ile sesli konusur.
- Ekran goruntusu alip Gemini Vision'a analiz ettirebilir.
- Apple Calendar ve Reminders okuyup yazabilir, etkinlik silebilir.
- WhatsApp mesaj taslagi acabilir veya otomatik gondermeyi deneyebilir.
- Terminal komutu calistirma araci icerir.
- Kullanici bilgilerini kalici bellekte saklar.

Bu yuzden "temiz gorunuyor" demek ile "risksiz" demek ayni sey degil. Ham haliyle Windows bilgisayarda calistirilmasini onermiyorum.

## Paket Yapisi

Dis ZIP:

- `BENI OKU.txt`
- `OZELLIKLER.txt`
- `Windows.txt`
- `README.md`
- `jarvis.zip`

Ic ZIP:

- `main.py`
- `ui.py`
- `app_config.py`
- `core/prompt.txt`
- `actions/*.py`
- `memory/*.py`
- `helpers/*.swift`
- `helpers/bin/jarvis-calendar-helper`
- `SFX/*.mp3`
- `Fonts/*.ttf`

## Hash Bilgileri

- `jarvis-main.zip`: `95FC886156EDFDE4DA4A811C6AB380EEBFADC8B183C326F600CCA61E2B26586F`
- ic `jarvis.zip`: `DD19A4AEA474648AF78D1879444736AC944074142BA56A581D4AE2D4349653BF`
- `helpers/bin/jarvis-calendar-helper`: `FF976A42392F59C64E206AE5209AE5E1702A929288701A112F13CE7F942C86F2`

## Guvenlik Bulgulari

### 1. Terminal komutu calistirma

Dosya: `_audit_jarvis_zip/extracted_jarvis/jarvis/actions/shell.py`

`shell_run(command)` fonksiyonu `subprocess.run(..., shell=True)` kullaniyor. Bazi tehlikeli komutlari engelliyor ama bu kara liste tam koruma sayilmaz.

Risk: Model yanlis anlarsa veya kotu niyetli bir prompt komut uretirse sistem komutu calisabilir.

Windows JARVIS'e tasima karari: Ham haliyle tasinmayacak. Sadece izinli komut listesiyle, onayli ve dar kapsamli olarak tasinir.

### 2. WhatsApp otomatik gonderme

Dosyalar:

- `_audit_jarvis_zip/extracted_jarvis/jarvis/core/prompt.txt`
- `_audit_jarvis_zip/extracted_jarvis/jarvis/actions/whatsapp.py`
- `_audit_jarvis_zip/extracted_jarvis/jarvis/main.py`

Prompt, kullanici "gonder/yolla" derse ekstra onay istemeden `send_now=true` kullanmayi soyluyor.

Risk: Yanlis duyulan bir isim veya mesaj otomatik gidebilir.

Windows JARVIS'e tasima karari: Otomatik gonderme kapali olacak. Once taslak acilacak, sonra ayrica onay istenecek.

### 3. Ekran goruntusu analizi

Dosyalar:

- `_audit_jarvis_zip/extracted_jarvis/jarvis/actions/screen_vision.py`
- `_audit_jarvis_zip/extracted_jarvis/jarvis/helpers/jarvis_screen_helper.swift`

Aktif pencerenin ekran goruntusunu alir, sonra Gemini Vision'a gonderir. Is bittikten sonra gecici goruntu dosyasini silmeye calisir.

Risk: Ekranda o anda ozel bilgi varsa dis API'ye gidebilir.

Windows JARVIS'e tasima karari: Sadece kullanici "ekrani analiz et" derse calisacak, oncesinde ekranda hassas bilgi uyarisi gosterilecek.

### 4. Takvim ve hatirlatici okuma/yazma/silme

Dosyalar:

- `_audit_jarvis_zip/extracted_jarvis/jarvis/actions/calendar.py`
- `_audit_jarvis_zip/extracted_jarvis/jarvis/actions/reminders.py`
- `_audit_jarvis_zip/extracted_jarvis/jarvis/helpers/jarvis_calendar_helper.swift`

Apple Calendar/Reminders uzerinden okuma, ekleme ve silme yapabiliyor.

Risk: Yanlis takvim etkinligi eklenebilir veya silinebilir.

Windows JARVIS'e tasima karari: Windows tarafinda once yerel `plans.json` ile baslayacagiz. Outlook/Google Calendar entegrasyonu daha sonra, ayrica onayli olacak.

### 5. Kalici bellek

Dosyalar:

- `_audit_jarvis_zip/extracted_jarvis/jarvis/memory/memory_manager.py`
- `_audit_jarvis_zip/extracted_jarvis/jarvis/core/prompt.txt`

Prompt, kullanici hakkinda onemli bilgi duyarsa sessizce bellekte saklamasini soyluyor.

Risk: Kullanici fark etmeden ozel bilgi kaydedilebilir.

Windows JARVIS'e tasima karari: Bellek paneli olacak. "Bunu hatirla" demedikce otomatik kayit yapmayacak.

### 6. API anahtarlari

Dosya: `_audit_jarvis_zip/extracted_jarvis/jarvis/app_config.py`

Gemini ve YouTube API anahtarlari `config/api_keys.json` icinde duz metin olarak saklaniyor. `.gitignore` dosyasi bunu disliyor, bu iyi. Ama yerel dosyada duz metin kalir.

Windows JARVIS'e tasima karari: Mevcut `.env` yapimiz korunacak. UI'da anahtar gosterilmeyecek.

## Temiz Gorunen Parcalar

- UI fikri ve HUD panel mantigi.
- SFX dosyalari teknik olarak normal ses dosyasi gorunuyor.
- Font ve ikon dosyalari normal asset olarak duruyor.
- Memory, calendar, media, weather gibi moduller islevsel olarak anlasilir.
- Bilinen dis baglantilar Gemini, YouTube API, YouTube arama, Google arama, wttr.in hava durumu, WhatsApp Web gibi beklenen servisler.

## Dikkat Edilecek Parcalar

- `helpers/bin/jarvis-calendar-helper` precompiled macOS binary. Kaynak Swift dosyasi var ama binary imzasini Windows ortaminda dogrulamadim.
- `shell_run` modeli gereksiz yetkili yapar.
- `send_whatsapp_message(send_now=true)` fazla rahat.
- `analyze_screen` ekrandaki bilgiyi API'ye gonderebilir.
- macOS `osascript`, `open`, `pbcopy`, `screencapture`, Apple Calendar/Reminder API'leri Windows'ta calismaz.

## Bizim JARVIS'e Tasima Karari

Ham kodu kopyalamayacagiz. Onun yerine fikirleri Windows'a ve senin kullanimina gore guvenli bicimde yeniden kuracagiz.

Oncelikli tasima sirasi:

1. Daha guclu ses algilama/transkripsiyon.
2. Gercek planlayici: `plans.json`, bugun/yarin/haftalik plan paneli.
3. Bellek paneli: sadece "bunu hatirla" denince kayit.
4. Ekran analizi: sadece acik onayla.
5. WhatsApp/mesaj sistemi: once taslak, sonra ayri onay.
6. Sistem komutlari: sadece izinli komut listesi.

## Net Tavsiye

Bu ZIP'i kendi basina calistirma. Kodu fikir kaynagi olarak kullanmak mantikli; ama yetki modeli ve macOS bagimliliklari yuzunden bizim Windows JARVIS icin guvenli sekilde yeniden yazmak daha dogru.
