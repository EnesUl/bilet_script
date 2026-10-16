"""
Cinema City Bilet Takipci
Gercek API endpoint kullanarak bilet acilisini takip eder.
"""

import logging
import sys
import time
import os
from datetime import datetime, date, timedelta

import requests
import schedule

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

# ------------------------------------------------------------------ #
# Logging                                                             #
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# Daha once bildirim gonderilen tarihler
notified_dates: set = set()

# ------------------------------------------------------------------ #
# HTTP Ayarlari                                                       #
# ------------------------------------------------------------------ #
BASE_API = "https://www.cinemacity.cz/cz/data-api-service/v1/quickbook/10101"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.cinemacity.cz/",
    "Origin": "https://www.cinemacity.cz",
})

# ------------------------------------------------------------------ #
# API Fonksiyonlari                                                   #
# ------------------------------------------------------------------ #

def get_available_dates() -> list:
    """
    Sinema icin bilet satilan tarihlerin listesini cekar.
    Ornek donus: ["2026-08-26", "2026-08-27", ..., "2026-09-08"]
    """
    url = f"{BASE_API}/dates/in-cinema/{config.CINEMA_ID}/until/2027-12-31"
    try:
        resp = SESSION.get(url, params={"attr": "", "lang": "en_GB"}, timeout=20)
        resp.raise_for_status()
        return resp.json().get("body", {}).get("dates", [])
    except Exception as e:
        log.error("Tarih listesi alinamadi: " + str(e))
        return []


def get_film_events_on_date(check_date: str) -> dict:
    """
    Belirtilen tarihteki film etkinliklerini cekar.
    {'films': [...], 'events': [...]} seklinde doner.
    """
    url = f"{BASE_API}/film-events/in-cinema/{config.CINEMA_ID}/at-date/{check_date}"
    try:
        resp = SESSION.get(url, params={"attr": "", "lang": "en_GB"}, timeout=20)
        resp.raise_for_status()
        body = resp.json().get("body", {})
        return {
            "films": body.get("films", []),
            "events": body.get("events", []),
        }
    except Exception as e:
        log.error("Film eventi alinamadi (" + check_date + "): " + str(e))
        return {"films": [], "events": []}


def is_target_film_available(check_date: str) -> tuple:
    """
    Hedef film o tarihte satista mi?
    (True/False, seans_listesi) doner.
    """
    data = get_film_events_on_date(check_date)
    films = data["films"]
    events = data["events"]

    # Film listesinde hedef film var mi?
    film_found = any(
        str(f.get("id", "")).lower() == config.MOVIE_ID.lower()
        for f in films
    )

    if not film_found:
        return False, []

    # O filme ait seanslar
    target_events = [
        e for e in events
        if str(e.get("filmId", "")).lower() == config.MOVIE_ID.lower()
    ]

    return True, target_events


# ------------------------------------------------------------------ #
# Telegram Bildirimi                                                  #
# ------------------------------------------------------------------ #

def send_telegram(message: str) -> bool:
    if config.TELEGRAM_BOT_TOKEN == "BURAYA_BOT_TOKENINI_YAZ":
        log.warning("Telegram token ayarlanmamis! config.py dosyasini guncelle.")
        return False

    url = "https://api.telegram.org/bot" + config.TELEGRAM_BOT_TOKEN + "/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            log.info("Telegram bildirimi gonderildi!")
            return True
        else:
            log.error("Telegram hata: " + str(resp.status_code) + " - " + resp.text[:200])
            return False
    except Exception as e:
        log.error("Telegram gonderim hatasi: " + str(e))
        return False


def format_showtime_info(events: list) -> str:
    """Seans saatlerini okunakli sekle getirir."""
    if not events:
        return ""
    lines = []
    for ev in events[:8]:  # max 8 seans goster
        start = ev.get("eventDateTime", "")
        screen = ev.get("screenName", "")
        attrs = ev.get("attributeIds", [])
        attr_str = ", ".join(attrs) if attrs else "Standard"
        if start:
            # "2026-09-09T14:30:00" -> "14:30"
            saat = start.split("T")[-1][:5] if "T" in start else start
            lines.append("  " + saat + " - " + screen + " (" + attr_str + ")")
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Ana Kontrol Fonksiyonu                                              #
# ------------------------------------------------------------------ #

def check_tickets():
    log.info("=" * 55)
    log.info("Bilet kontrolu baslatildi...")

    watch_start = datetime.strptime(config.WATCH_FROM_DATE, "%Y-%m-%d").date()

    # Adim 1: Mevcut tum tarihleri cek
    available_dates = get_available_dates()
    if not available_dates:
        log.warning("Tarih listesi alinamadi, bir sonraki kontrolde tekrar denenecek.")
        return

    log.info("Mevcut son tarih: " + (available_dates[-1] if available_dates else "?"))

    # Adim 2: Takip tarihlerini filtrele
    watch_dates = [
        d for d in available_dates
        if datetime.strptime(d, "%Y-%m-%d").date() >= watch_start
    ]

    # Adim 3: Listede yoksa ama ileriye dek kontrol et
    if not watch_dates:
        # Tarihlerde gorunmuyor - belki heniiz acilmadi
        # Yaklasan tarihleri de dogrudan dene (bazen listede olmadan acilabilir)
        for i in range(3):
            d = (watch_start + timedelta(days=i)).strftime("%Y-%m-%d")
            if d not in notified_dates:
                found, events = is_target_film_available(d)
                if found and events:
                    watch_dates.append(d)

    if not watch_dates:
        log.info("9 Eylul ve sonrasi icin henuz bilet acilmamis.")
        return

    # Adim 4: Bulunan tarihleri kontrol et ve bildir
    log.info(str(len(watch_dates)) + " tarih kontrol edilecek: " + str(watch_dates))

    for date_str in watch_dates:
        if date_str in notified_dates:
            log.info("  " + date_str + ": Zaten bildirildi, atlaniyor.")
            continue

        found, events = is_target_film_available(date_str)

        if found:
            log.info("  *** BILET BULUNDU: " + date_str + " ***")
            notified_dates.add(date_str)

            gun = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %d %B %Y")
            showtime_text = format_showtime_info(events)

            ticket_url = (
                "https://www.cinemacity.cz/cinemas/flora/" + config.CINEMA_ID +
                "?lang=en_GB"
                "#/buy-tickets-by-cinema?in-cinema=" + config.CINEMA_ID +
                "&at=" + date_str +
                "&for-movie=" + config.MOVIE_ID +
                "&view-mode=list"
            )

            msg_lines = [
                "BILET ACILDI!",
                "",
                "Tarih: " + gun,
                "Sinema: " + config.CINEMA_NAME,
                "Film: The Odyssey",
            ]
            if showtime_text:
                msg_lines.append("")
                msg_lines.append("Seans saatleri:")
                msg_lines.append(showtime_text)
            msg_lines.append("")
            msg_lines.append("Bilet almak icin:")
            msg_lines.append(ticket_url)

            msg = "\n".join(msg_lines)
            send_telegram(
                "<b>BILET ACILDI!</b>\n\n"
                "Tarih: <b>" + gun + "</b>\n"
                "Sinema: " + config.CINEMA_NAME + "\n"
                "Film: <b>The Odyssey</b>\n\n"
                + ("<b>Seans saatleri:</b>\n" + showtime_text + "\n\n" if showtime_text else "") +
                '<a href="' + ticket_url + '">Hemen Bilet Al!</a>'
            )
        else:
            log.info("  " + date_str + ": Film bu tarihte yok.")

    log.info("Kontrol tamamlandi.")
    log.info("Bir sonraki kontrol: " + str(config.CHECK_INTERVAL_MINUTES) + " dakika sonra.")


# ------------------------------------------------------------------ #
# Baslangic                                                           #
# ------------------------------------------------------------------ #

def main():
    log.info("*" * 55)
    log.info("  Cinema City Bilet Takipci baslatildi")
    log.info("*" * 55)
    log.info("Film      : The Odyssey (" + config.MOVIE_ID + ")")
    log.info("Sinema    : " + config.CINEMA_NAME)
    log.info("Takip     : " + config.WATCH_FROM_DATE + " tarihinden itibaren")
    log.info("Aralik    : Her " + str(config.CHECK_INTERVAL_MINUTES) + " dakikada bir")
    log.info("-" * 55)

    if config.TELEGRAM_BOT_TOKEN == "BURAYA_BOT_TOKENINI_YAZ":
        log.warning("!" * 55)
        log.warning("DIKKAT: config.py dosyasinda Telegram token eksik!")
        log.warning("config.py icindeki TELEGRAM_BOT_TOKEN ve")
        log.warning("TELEGRAM_CHAT_ID degerlerini guncelle.")
        log.warning("!" * 55)
    else:
        # Baslangicta test mesaji gonder
        send_telegram(
            "Bilet takipci baslatildi!\n\n"
            "Film: The Odyssey\n"
            "Tarih: " + config.WATCH_FROM_DATE + " ve sonrasi\n"
            "Kontrol: Her " + str(config.CHECK_INTERVAL_MINUTES) + " dakikada bir"
        )

    # Ilk kontrol hemen
    check_tickets()

    # Sonraki kontroller zamanlayiciya gore
    schedule.every(config.CHECK_INTERVAL_MINUTES).minutes.do(check_tickets)

    log.info("Zamanlayici aktif. Durdurmak icin Ctrl+C.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Program kullanici tarafindan durduruldu.")


if __name__ == "__main__":
    main()
