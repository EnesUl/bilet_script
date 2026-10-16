# Cinema City Bilet Takipci
**The Odyssey** filmi icin Prague Flora sinemasinda 9 Eylul ve sonrasi
biletler acildiginda aninda Telegram bildirimi gonderir.

## Kurulum (5 dakika)

### 1. Telegram Bot Kur
1. Telegramdan **@BotFather**a yaz, `/newbot` komutunu gonder
2. Bot ismi ver (ornek: CinemaBot)
3. Aldign **token**i kopyala
4. Telegramdan **@userinfobot**a `/start` gonder, **chat_id**ni al

### 2. config.py Dosyasini Olustur
`config.example.py` dosyasini `config.py` olarak kopyala (config.py git tarafindan yoksayilir, token asla paylasilmaz).
`config.py` dosyasini Not Defteri ile ac ve su satirlari doldur:
```
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGhIJKlmNOPqrsTUVwxyz"
TELEGRAM_CHAT_ID   = "123456789"
```

### 3. Programi Calistir
`CALISTIR.bat` dosyasina cift tikla.

## Dosyalar
| Dosya | Aciklama |
|---|---|
| `config.example.py` | Ayar sablonu (kopyalayip `config.py` yap) |
| `takipci.py` | Ana program |
| `CALISTIR.bat` | Programi baslatir |
| `bilet_takip.log` | Log kayitlari |

## Nasil Calisir?
- Her **15 dakikada bir** Cinema City API'sini sorgular
- 9 Eylul veya sonrasi icin bilet acildiginda **aninda Telegram mesaji** gonderir
- Ayni tarih icin birden fazla bildirim gondermez
- API: `cinemacity.cz/cz/data-api-service/v1/quickbook/10101/...`

## Ornek Telegram Bildirimi
```
BILET ACILDI!

Tarih: Wednesday, 09 September 2026
Sinema: Prague Flora, OC FLORA
Film: The Odyssey

Seans saatleri:
  14:30 - Screen 1 (2D)
  17:00 - IMAX (IMAX)
  20:15 - Screen 3 (3D)

Hemen Bilet Al! -> [link]
```

## Arka Planda Calistirmak
Bilgisayar kapaninca program durur. Surekli calistirmak icin:
- **Gorev Zamanlayicisi** (Task Scheduler) ile baslangicta otomatik calistir
- Veya bilgisayari uyku moduna alirken "Calistir.bat"i acik birak
