import asyncio
import base64
import ctypes
import datetime as dt
import io
import json
import math
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
import webbrowser
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

import pyautogui
import speech_recognition as sr
from dotenv import load_dotenv
from openai import OpenAI
from PyQt6.QtCore import QBuffer, QIODevice, QObject, QPoint, QRectF, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QFileDialog, QLineEdit, QPushButton, QTextEdit, QWidget

from jarvis_brain import JarvisBrain, QUESTION_MARKERS, is_question_like, normalize_text

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None

try:
    import psutil
except Exception:
    psutil = None

try:
    import pygetwindow as gw
except Exception:
    gw = None

try:
    import pyperclip
except Exception:
    pyperclip = None

try:
    import edge_tts
    import pygame
except Exception:
    edge_tts = None
    pygame = None

try:
    import openwakeword
    import numpy as np
    import pyaudio
    from openwakeword.model import Model
except Exception:
    openwakeword = None
    np = None
    pyaudio = None
    Model = None


BASE_DIR = Path(__file__).resolve().parent
# ESKİ → güncellendi
APP_VERSION = "v2.9.2"
COORD_FILE = BASE_DIR / "coords.json"
LOL_ASSISTANT_FILE = BASE_DIR / "lol_assistant.json"
PLAN_FILE = BASE_DIR / "plans.json"
MEMORY_FILE = BASE_DIR / "jarvis_memory.json"
LOG_FILE = BASE_DIR / "jarvis_log.txt"
VOICE = "tr-TR-EmelNeural"
VOICE_RATE = "+20%"
VOICE_PITCH = "+5Hz"
WAKE_THRESHOLD = 0.15
CHUNK = 1280
# ESKI -> guncellendi
JARVIS_RESPONSE_SYSTEM_PROMPT = """
Sen J.A.R.V.I.S.'sin.

KISILIGIN:
- Yuksek zekali, durust, analitik
- Koru korune onaylamiyorsun
- Kullanici hata yapiyorsa kibarca ama net uyariyorsun
- Gerektiginde itiraz ediyorsun
- Ogretmen ve destekci rolundesin
- Kisa ve oz konusuyorsun ama onemli seyleri atlamiyorsun
- Turkce konusuyorsun
- Kullaniciya her zaman 'Efendim' diye hitap ediyorsun

HAFIZANDAN KULLAN:
{memory_context}

DAVRANIS KURALLARI:
- Bir sey sorulursa once dusun, sonra cevapla
- Riskli bir sey istenirse uyar: 'Efendim, bunu yaparsaniz su sonuc cikabilir'
- Yanlis bilgi verilirse duzelt
- Ogretici ol; sadece cevap verme, neden oyle oldugunu da acikla
- Kullanicinin aliskanliklarini ogren ve hatirla
- Uzun konusmalarda baglami koru
""".strip()

load_dotenv(BASE_DIR / ".env")


def env_float(name, default, minimum=None, maximum=None):
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = float(default)
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def env_int(name, default, minimum=None, maximum=None):
    try:
        value = int(float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        value = int(default)
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


VOICE = os.getenv("JARVIS_VOICE", VOICE)
VOICE_RATE = os.getenv("VOICE_RATE", VOICE_RATE)
VOICE_PITCH = os.getenv("VOICE_PITCH", VOICE_PITCH)
WAKE_THRESHOLD = env_float("WAKE_THRESHOLD", WAKE_THRESHOLD, 0.01, 1.0)
CHUNK = env_int("WAKE_CHUNK", CHUNK, 320, 4096)
MIC_ENERGY_THRESHOLD = env_int("MIC_ENERGY_THRESHOLD", 220, 50, 4000)
MIC_PAUSE_THRESHOLD = env_float("MIC_PAUSE_THRESHOLD", 1.05, 0.2, 3.0)
MIC_NON_SPEAKING_DURATION = env_float("MIC_NON_SPEAKING_DURATION", 0.45, 0.1, 2.0)
MIC_AMBIENT_DURATION = env_float("MIC_AMBIENT_DURATION", 0.7, 0.1, 3.0)
VOICE_VOLUME_PERCENT = env_int("VOICE_VOLUME_PERCENT", 22, 5, 100)
JARVIS_SIMPLE_MODEL = os.getenv("JARVIS_SIMPLE_MODEL", "gpt-4.1-mini")
JARVIS_COMPLEX_MODEL = os.getenv("JARVIS_COMPLEX_MODEL", "gpt-4o")
JARVIS_SIMPLE_MAX_TOKENS = env_int("JARVIS_SIMPLE_MAX_TOKENS", 300, 80, 2000)
JARVIS_COMPLEX_MAX_TOKENS = env_int("JARVIS_COMPLEX_MAX_TOKENS", 1000, 200, 4000)
JARVIS_SIMPLE_TEMPERATURE = env_float("JARVIS_SIMPLE_TEMPERATURE", 0.7, 0.0, 2.0)
JARVIS_COMPLEX_TEMPERATURE = env_float("JARVIS_COMPLEX_TEMPERATURE", 0.5, 0.0, 2.0)


def norm(text):
    return normalize_text(text)


def clean_query(text):
    words_to_remove = [
        "youtube",
        "youtubedan",
        "youtube dan",
        "youtubeu",
        "youtubeyi",
        "spotify",
        "spotfy",
        "spotifydan",
        "spotify dan",
        "google",
        "googledan",
        "google dan",
        "dan",
        "den",
        "da",
        "de",
        "ac",
        "ara",
        "bak",
        "izle",
        "cal",
        "bul",
        "gir",
        "uzerinden",
        "bakar misin",
        "acar misin",
    ]
    for word in words_to_remove:
        text = text.replace(word, "")
    return " ".join(text.split()).strip()


def clean_music_query(text):
    text = norm(text)
    words_to_remove = [
        "spotify", "spotfy", "spotifydan", "spotify den", "spotify da", "spotifyde",
        "uygulamasinda", "uygulamasina", "uygulamada", "uygulama", "appta", "appte",
        "sarkisini", "sarkiyi", "sarki", "muzik", "parca", "track",
        "baslat", "ac", "cal", "dinle", "bul", "ara", "gir", "oradan", "orda", "olur",
        "den", "dan", "de", "da", "ki", "ve", "onu", "bunu",
    ]
    for word in words_to_remove:
        text = text.replace(word, " ")
    return " ".join(text.split()).strip()


class JarvisCore(QObject):
    log = pyqtSignal(str)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool)
    speaking = pyqtSignal(bool)
    ui_command = pyqtSignal(str)

    GAME_SAFE_KILL = [
        "chrome.exe",
        "opera.exe",
        "msedge.exe",
        "firefox.exe",
        "roblox.exe",
        "steam.exe",
        "epicgameslauncher.exe",
        "code.exe",
        "codex.exe",
    ]
    GAME_VALORANT_EXTRA_KILL = ["spotify.exe"]
    GAME_PROTECTED_PROCESSES = {
        "riotclientservices.exe",
        "riotclientux.exe",
        "riotclientuxrender.exe",
        "leagueclient.exe",
        "leagueclientux.exe",
        "league of legends.exe",
        "valorant.exe",
        "valorant-win64-shipping.exe",
        "vgc.exe",
        "vgtray.exe",
        "discord.exe",
        "python.exe",
        "python3.exe",
        "pythonw.exe",
        "jarvis.exe",
        "jarvis_app.exe",
    }

    def __init__(self):
        super().__init__()
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.brain = JarvisBrain(
            client=self.client,
            model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
            memory_path=MEMORY_FILE,
        )
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = MIC_ENERGY_THRESHOLD
        self.recognizer.pause_threshold = MIC_PAUSE_THRESHOLD
        self.recognizer.non_speaking_duration = MIC_NON_SPEAKING_DURATION
        self.pending_action = None
        self.last_meaningful_command = None
        self.last_research_subject = None
        self.last_spotify_query = None
        self.attached_file_path = None
        self.last_action_summary = "Henuz ozel bir islem yapmadim."
        self.conversation_history = []
        self.v3_enabled = True
        self.shutdown_warning_thread = None
        self.screen_watch_thread = None
        self.screen_watch_stop = threading.Event()
        self.screen_watch_until = 0
        self.screen_capture_warning_shown = False
        self.speech_stop_requested = False
        self.speak_lock = threading.Lock()
        self.voice_volume = VOICE_VOLUME_PERCENT / 100
        self.quiet_mode = False
        self.mode = "AKTIF"
        self.current_game_profile = None
        self.pyautogui_enabled = True
        self.game_mode_watch_stop = threading.Event()
        self.game_mode_watch_thread = None
        self.game_mode_target_seen = False
        self.last_model_used = None
        self.last_night_warning_key = None
        self.log_event("INFO", f"Jarvis baslatildi {APP_VERSION}")

    def record_command_result(self, command, route, result="", success=True):
        model_or_route = self.last_model_used or route or "yerel"
        safe_command = str(command or "").replace("\n", " ").strip()
        self.log_event("KOMUT", f"\"{safe_command}\" -> {model_or_route}")
        try:
            self.brain.record_command(command, route, result, success=success)
        except Exception as exc:
            self.log.emit(f"> OGRENME HATASI: {exc}")
            self.log_event("HATA", f"Ogrenme hatasi: {exc}")

    def log_event(self, level, message):
        timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{str(level).upper()}] {message}\n"
        try:
            with LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass

    def log_shutdown(self):
        self.log_event("INFO", f"Jarvis kapatildi {APP_VERSION}")

    def open_edge_private_urls(self, urls, gap=0.6):
        for url in urls:
            os.system(f'start msedge -inprivate "{url}"')
            time.sleep(gap)

    def open_opera_url(self, url, fullscreen=False, side_screen=False):
        os.system(f'start opera "{url}"')

        if fullscreen or side_screen:
            def arrange():
                time.sleep(2.5)
                if side_screen:
                    pyautogui.hotkey("win", "shift", "right")
                    time.sleep(0.5)
                if fullscreen:
                    pyautogui.press("f11")

            threading.Thread(target=arrange, daemon=True).start()

    def check_kick_live(self, channel):
        channel = re.sub(r"[^a-zA-Z0-9_\\-]", "", channel.strip())
        if not channel:
            return None

        endpoints = [
            f"https://kick.com/api/v2/channels/{channel}",
            f"https://kick.com/api/v1/channels/{channel}",
        ]

        for endpoint in endpoints:
            try:
                request = urllib.request.Request(
                    endpoint,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(request, timeout=8) as response:
                    data = json.loads(response.read().decode("utf-8", errors="ignore"))
                return bool(data.get("livestream"))
            except Exception:
                continue

        return None

    def extract_kick_channel(self, text):
        clean = norm(text)
        for marker in ["kick i ac", "kick ac", "kick.com", "kick"]:
            clean = clean.replace(marker, " ")
        for phrase in [
            "operadan",
            "opera",
            "yayinda mi",
            "yayindaysa",
            "yayini",
            "tam ekran",
            "yan ekrana koy",
            "yan ekran",
            "bak",
            "ac",
            "gir",
        ]:
            clean = clean.replace(phrase, " ")
        words = [word for word in clean.split() if len(word) > 1]
        return words[0] if words else None

    def open_kick(self, channel=None, browser="opera", fullscreen=False, side_screen=False, check_live=False):
        url = "https://kick.com" if not channel else f"https://kick.com/{channel}"
        live = self.check_kick_live(channel) if channel and check_live else None

        if browser == "opera":
            self.open_opera_url(url, fullscreen=fullscreen and live is not False, side_screen=side_screen and live is not False)
        else:
            webbrowser.open(url)

        if channel and live is True:
            return f"{channel} Kick'te yayinda gorunuyor. Sayfayi actim."
        if channel and live is False:
            return f"{channel} Kick'te su an yayinda gorunmuyor. Yine de kanal sayfasini actim."
        if channel:
            return f"{channel} Kick sayfasini actim. Yayinda olup olmadigini sayfadan kontrol edebilirsin."
        return "Kick acildi."

    def make_search_urls(self, query, include_social=False, include_images=False, include_youtube=False):
        encoded = urllib.parse.quote(query)
        urls = ["https://www.google.com/search?q=" + encoded]

        if include_images:
            urls.append("https://www.google.com/search?tbm=isch&q=" + encoded)

        if include_youtube:
            urls.append("https://www.youtube.com/results?search_query=" + encoded)

        if include_social:
            for site in ["instagram.com", "tiktok.com", "youtube.com", "facebook.com", "x.com", "linkedin.com"]:
                urls.append("https://www.google.com/search?q=" + urllib.parse.quote(f"{query} site:{site}"))

        return urls

    def extract_subject_after_markers(self, text, markers):
        clean = norm(text)
        for marker in markers:
            if marker in clean:
                clean = clean.split(marker, 1)[1]
                break

        junk_phrases = [
            "icin yap",
            "tum internette",
            "tum sosyal aglarda",
            "sosyal aglarda",
            "sosyal medyada",
            "instagram",
            "youtube",
            "yotube",
            "tiktok",
            "ve",
            "facebook",
            "twitter",
            "linkedin",
            "bu adami",
            "adami",
            "yip",
            "ara",
            "arayip",
            "bul",
            "kim oldugunu",
            "bana anlat",
            "anlat",
            "gorselini ac",
            "resmini ac",
        ]
        for phrase in junk_phrases:
            clean = clean.replace(phrase, " ")

        return " ".join(clean.split()).strip()

    def run_powershell(self, command, timeout=1800):
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (completed.stdout or completed.stderr or "").strip()
        return completed.returncode, output

    def defender_status_summary(self):
        command = (
            "$s=Get-MpComputerStatus; "
            "$t=Get-MpThreat; "
            "$quick=if($s.QuickScanEndTime){$s.QuickScanEndTime.ToString('yyyy-MM-dd HH:mm:ss')}else{'bilinmiyor'}; "
            "$full=if($s.FullScanEndTime){$s.FullScanEndTime.ToString('yyyy-MM-dd HH:mm:ss')}else{'bilinmiyor'}; "
            "[pscustomobject]@{"
            "AntivirusEnabled=$s.AntivirusEnabled;"
            "RealTimeProtectionEnabled=$s.RealTimeProtectionEnabled;"
            "LastQuickScan=$quick;"
            "LastFullScan=$full;"
            "ThreatCount=($t | Measure-Object).Count"
            "} | ConvertTo-Json -Compress"
        )
        code, output = self.run_powershell(command, timeout=30)
        if code != 0 or not output:
            return "Windows Defender durumu okunamadi. Windows Guvenligi uygulamasini acip elle kontrol edebilirsin."
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return "Windows Defender durumunu okudum ama sonucu anlayamadim."

        active = data.get("AntivirusEnabled")
        realtime = data.get("RealTimeProtectionEnabled")
        threats = data.get("ThreatCount", 0)
        quick = data.get("LastQuickScan") or "bilinmiyor"
        if isinstance(quick, str) and quick.startswith("/Date("):
            match = re.search(r"\d+", quick)
            if match:
                timestamp = int(match.group(0)) / 1000
                quick = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        if threats:
            return f"Defender aktif: {active}. Gercek zamanli koruma: {realtime}. {threats} tehdit kaydi gorunuyor. Windows Guvenligi'nde ayrintilari acmani oneririm."
        return f"Defender aktif: {active}. Gercek zamanli koruma: {realtime}. Kayitli tehdit gorunmuyor. Son hizli tarama: {quick}."

    def start_defender_scan(self, scan_type):
        ps_type = "FullScan" if scan_type == "full" else "QuickScan"
        label = "tam" if scan_type == "full" else "hizli"
        self.speak(f"Windows Defender {label} tarama baslatiliyor. Bu islem biraz surebilir.")
        code, output = self.run_powershell(f"Start-MpScan -ScanType {ps_type}", timeout=7200)
        if code != 0:
            return f"Defender {label} tarama baslatilamadi: {output[:240]}"
        return f"Windows Defender {label} tarama tamamlandi. " + self.defender_status_summary()

    def open_spotify_app_search(self, query, autoplay=False):
        query = " ".join(query.split()).strip()
        if not query:
            return "Hangi sarkiyi acacagimi anlayamadim."

        self.last_spotify_query = query
        os.system(f'start "" "spotify:search:{urllib.parse.quote(query)}"')

        if autoplay:
            def try_play():
                time.sleep(2.5)
                pyautogui.hotkey("alt", "tab")
                time.sleep(0.6)
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.2)
                pyautogui.write(query, interval=0.02)
                time.sleep(0.2)
                pyautogui.press("enter")
                time.sleep(1.2)

                for _ in range(5):
                    pyautogui.press("tab")
                    time.sleep(0.12)

                pyautogui.press("enter")
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(0.5)
                pyautogui.press("playpause")

            threading.Thread(target=try_play, daemon=True).start()
            return f"Spotify uygulamasinda {query} araniyor. Ilk sonucu oynatmayi deniyorum."

        return f"Spotify uygulamasinda {query} araniyor."

    def copy_active_url(self):
        clipboard = QApplication.clipboard()
        previous = clipboard.text()
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        copied = clipboard.text().strip()
        if previous and copied == previous:
            time.sleep(0.25)
            copied = clipboard.text().strip()
        return copied

    def copy_selected_text(self):
        clipboard = QApplication.clipboard()
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)
        return clipboard.text().strip()

    def translate_current_site(self):
        url = self.copy_active_url()
        if not (url.startswith("http://") or url.startswith("https://")):
            return "Aktif sekmede cevrilecek bir web adresi bulamadim. Once sayfayi acip tekrar dene."

        translated_url = "https://translate.google.com/translate?sl=auto&tl=tr&u=" + urllib.parse.quote(url, safe="")
        webbrowser.open(translated_url)
        return "Sayfayi Turkce ceviri modunda actim."

    def translate_selected_text(self):
        selected = self.copy_selected_text()
        if not selected:
            return "Cevirmek icin once ekrandaki yaziyi secmelisin."

        if len(selected) > 3500:
            selected = selected[:3500]

        if not self.client:
            url = "https://translate.google.com/?sl=auto&tl=tr&text=" + urllib.parse.quote(selected) + "&op=translate"
            webbrowser.open(url)
            return "Secili yazi icin Google Translate actim."

        return self.chat_completion_text(
            [
                {"role": "system", "content": "Metni dogal, akici ve kisa Turkceye cevir. Sadece ceviriyi yaz."},
                {"role": "user", "content": selected},
            ]
        )

    def spotify_query_from_text(self, text):
        query = clean_music_query(text)

        if "kitaplik" in text or "playlist" in text or "liste" in text:
            query = query.replace("kitapliktan", " ").replace("kitaplik", " ")
            query = query.replace("playlistten", " ").replace("playlist", " ")
            query = query.replace("listeden", " ").replace("liste", " ")
            query = query.replace("rastgele", " ")
            query = " ".join(query.split()).strip()

        return query

    def load_lol_settings(self):
        defaults = {"enabled": False, "favorite_champion": None, "role": "mid"}
        if not LOL_ASSISTANT_FILE.exists():
            return defaults
        try:
            with LOL_ASSISTANT_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
            defaults.update(data)
        except (OSError, json.JSONDecodeError):
            pass
        return defaults

    def save_lol_settings(self, settings):
        with LOL_ASSISTANT_FILE.open("w", encoding="utf-8") as file:
            json.dump(settings, file, indent=2, ensure_ascii=False)

    def detect_lol_role(self, text):
        role_map = {
            "top": ["top", "ust", "solo"],
            "jungle": ["jungle", "orman", "jg"],
            "mid": ["mid", "orta"],
            "adc": ["adc", "bot", "bottom", "nişanci", "nisanci"],
            "support": ["support", "sup", "destek"],
        }
        for role, aliases in role_map.items():
            if any(alias in text for alias in aliases):
                return role
        return None

    def extract_lol_champion(self, text):
        clean = norm(text)
        for phrase in [
            "lol yardim modu",
            "lol modu",
            "favori sampiyon kaydet",
            "favori hero kaydet",
            "sampiyon kaydet",
            "hero kaydet",
            "runlerini ac",
            "run ac",
            "build ac",
            "build sayfasi ac",
            "hazirla",
            "icin",
            "rune",
            "run",
            "runes",
            "champion",
            "sampiyon",
            "hero",
            "league of legends",
            "lol",
            "opgg",
            "u gg",
            "ugg",
            "ac",
        ]:
            clean = clean.replace(phrase, " ")

        for role_word in ["top", "ust", "solo", "jungle", "orman", "jg", "mid", "orta", "adc", "bot", "bottom", "nisanci", "support", "sup", "destek"]:
            clean = clean.replace(role_word, " ")

        return " ".join(clean.split()).strip()

    def champion_slug(self, champion):
        aliases = {
            "wukong": "monkeyking",
            "nunu": "nunu",
            "nunu willump": "nunu",
            "jarvan": "jarvaniv",
            "jarvan iv": "jarvaniv",
            "k sante": "ksante",
            "ksante": "ksante",
            "dr mundo": "drmundo",
            "mundo": "drmundo",
            "miss fortune": "missfortune",
            "twisted fate": "twistedfate",
            "master yi": "masteryi",
            "lee sin": "leesin",
            "tahm kench": "tahmkench",
            "aurelion sol": "aurelionsol",
            "renata glasc": "renata",
            "bel veth": "belveth",
            "vel koz": "velkoz",
            "cho gath": "chogath",
            "kai sa": "kaisa",
            "kha zix": "khazix",
            "rek sai": "reksai",
        }
        key = " ".join(norm(champion).split())
        return aliases.get(key, re.sub(r"[^a-z0-9]", "", key))

    def open_lol_helper(self, champion=None, role=None):
        settings = self.load_lol_settings()
        champion = champion or settings.get("favorite_champion")
        role = role or settings.get("role") or "mid"

        if not champion:
            return "Hangi sampiyonu hazirlayacagimi soylemelisin. Ornek: yasuo mid hazirla."

        settings["favorite_champion"] = champion
        settings["role"] = role
        self.save_lol_settings(settings)

        slug = self.champion_slug(champion)
        search_query = urllib.parse.quote(f"{champion} {role} runes build")
        urls = [
            f"https://u.gg/lol/champions/{slug}/build/{role}",
            f"https://www.google.com/search?q={search_query}+site%3Aop.gg",
            f"https://www.google.com/search?q={search_query}+site%3Alolalytics.com",
        ]
        self.open_edge_private_urls(urls, gap=0.4)
        return f"{champion} icin {role} run ve build sayfalarini actim. Kabul ve kilitleme islemini manuel yap; ben hesap riski olan tiklamalari otomatik yapmiyorum."

    def parse_delay_seconds(self, text, default_seconds=10):
        match = re.search(r"(\d+)\s*(saniye|sn|dakika|dk|saat)", text)
        if not match:
            return default_seconds

        amount = int(match.group(1))
        unit = match.group(2)
        if unit in ["saniye", "sn"]:
            return amount
        if unit in ["dakika", "dk"]:
            return amount * 60
        if unit == "saat":
            return amount * 3600
        return default_seconds

    def format_delay(self, seconds):
        if seconds >= 3600 and seconds % 3600 == 0:
            return f"{seconds // 3600} saat"
        if seconds >= 60 and seconds % 60 == 0:
            return f"{seconds // 60} dakika"
        return f"{seconds} saniye"

    def schedule_shutdown_warning(self, delay_seconds, warning_seconds):
        if warning_seconds <= 0 or delay_seconds <= warning_seconds:
            return

        def warn():
            time.sleep(delay_seconds - warning_seconds)
            self.speak(
                f"Kapanmaya {warning_seconds} saniye kaldi. Iptal etmek istersen 'iptal et' de. Devam etsin istersen bir sey yapmana gerek yok.",
                force=True,
            )

        threading.Thread(target=warn, daemon=True).start()

    def load_coords(self):
        if not COORD_FILE.exists():
            return {}
        try:
            with COORD_FILE.open("r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            return {}

    def save_coords(self, coords):
        with COORD_FILE.open("w", encoding="utf-8") as file:
            json.dump(coords, file, indent=2, ensure_ascii=False)

    def plan_date_key(self, scope="bugun"):
        today = dt.date.today()
        if str(scope).lower() in ["yarin", "tomorrow", "yarın"]:
            today = today + dt.timedelta(days=1)
        return today.isoformat()

    def load_plans(self):
        if not PLAN_FILE.exists():
            return {"days": {}}
        try:
            data = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"days": {}}
        if not isinstance(data, dict):
            return {"days": {}}
        data.setdefault("days", {})
        return data

    def save_plans(self, plans):
        PLAN_FILE.write_text(json.dumps(plans, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_plan_items(self, scope="bugun"):
        plans = self.load_plans()
        key = self.plan_date_key(scope)
        items = plans.get("days", {}).get(key, [])
        return items if isinstance(items, list) else []

    def add_plan_item(self, scope, title, hour="", minute="00"):
        title = " ".join(str(title or "").split()).strip(" .,-")
        if not title:
            return "Plana eklenecek gorevi anlayamadim."
        key = self.plan_date_key(scope)
        plans = self.load_plans()
        days = plans.setdefault("days", {})
        items = days.setdefault(key, [])
        time_text = ""
        if hour:
            time_text = f"{int(hour):02d}:{int(minute or 0):02d}"
        item = {
            "time": time_text,
            "title": title,
            "done": False,
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        items.append(item)
        items.sort(key=lambda entry: (entry.get("time") or "99:99", entry.get("title") or ""))
        self.save_plans(plans)
        label = "Yarinin" if str(scope).lower().startswith("yar") else "Bugunun"
        if time_text:
            return f"{label} planina {time_text} icin '{title}' eklendi."
        return f"{label} planina '{title}' eklendi."

    def format_plan_summary(self, scope="bugun"):
        items = self.get_plan_items(scope)
        label = "yarin" if str(scope).lower().startswith("yar") else "bugun"
        if not items:
            return f"{label.title()} icin kayitli plan yok. Yeni bir sey eklemek ister misin?"
        lines = []
        for item in items[:6]:
            prefix = item.get("time") or "saat yok"
            lines.append(f"{prefix}: {item.get('title', '')}")
        return f"{label.title()} planin: " + " | ".join(lines)

    def remember_dialog(self, role, content):
        content = str(content or "").strip()
        if not content:
            return
        self.conversation_history.append({"role": role, "content": content})
        self.conversation_history = self.conversation_history[-12:]

    def jarvis_system_prompt(self):
        memory_context = self.brain.build_memory_context() if hasattr(self.brain, "build_memory_context") else ""
        if not memory_context:
            memory_context = "Kayit yok."
        return JARVIS_RESPONSE_SYSTEM_PROMPT.replace("{memory_context}", memory_context)

    def learn_from_exchange_async(self, user_text, assistant_text):
        if not self.client:
            return
        user_text = str(user_text or "").strip()
        assistant_text = str(assistant_text or "").strip()
        if not user_text or not assistant_text:
            return

        def worker():
            try:
                response = self.client.chat.completions.create(
                    model=os.getenv("JARVIS_LEARNING_MODEL", JARVIS_SIMPLE_MODEL),
                    max_tokens=80,
                    temperature=0,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Bu konusmadan kullanici hakkinda ogrenilen yeni bir bilgi var mi? "
                                "Varsa tek cumleyle yaz. Yoksa sadece 'yok' de. "
                                "Sifre, API anahtari, hassas hesap bilgisi veya ozel kisi takip bilgisi kaydetme."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Kullanici: {user_text}\nJARVIS: {assistant_text}",
                        },
                    ],
                )
                learned = (response.choices[0].message.content or "").strip()
                if learned and norm(learned) != "yok":
                    if self.brain.add_learned_info(learned):
                        self.log_event("HAFIZA", f"Yeni bilgi ogrenildi: {learned}")
                        self.log.emit(f"> HAFIZA: Yeni bilgi ogrenildi: {learned}")
            except Exception as exc:
                self.log_event("HATA", f"Hafiza ogrenme hatasi: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def check_warnings(self, command, current_time=None):
        current_time = current_time or dt.datetime.now()
        clean = norm(command)
        warnings = []

        if "sil" in clean and not any(word in clean for word in ["onayliyorum", "bunu yap", "eminim"]):
            warnings.append("Efendim, silme islemi geri alinamaz. Emin misiniz?")

        if self.mode == "OYUN" and any(word in clean for word in ["pyautogui", "tikla", "mouse", "otomatik kabul", "otomasyon"]):
            warnings.append("Efendim, oyun modunda ekrana otomasyon yaptirmak ban riski olusturabilir.")

        hour = current_time.hour
        night_key = current_time.strftime("%Y-%m-%d-%H")
        if 2 <= hour <= 6 and getattr(self, "last_night_warning_key", None) != night_key:
            warnings.append("Efendim, gec saatte calisiyorsunuz. Uyumanizi oneririm.")
            self.last_night_warning_key = night_key

        token_budget = env_int("JARVIS_TOKEN_MONTHLY_WARNING", 0, 0, 100000000)
        token_used = env_int("JARVIS_TOKEN_MONTHLY_USED", 0, 0, 100000000)
        if token_budget and token_used >= token_budget:
            warnings.append("Efendim, bu ay token harcamaniz belirlediginiz sinira yaklasti veya asti.")

        for warning in warnings:
            self.log_event("UYARI", f"Kullanici uyarildi: {warning}")
            try:
                self.brain.add_warning(warning)
            except Exception:
                pass
        return warnings

    def manager_context(self):
        today = self.format_plan_summary("bugun")
        tomorrow = self.format_plan_summary("yarin")
        return (
            f"Tarih/saat: {dt.datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"Son kullanici komutu: {self.last_meaningful_command or 'yok'}\n"
            f"Son islem ozeti: {self.last_action_summary}\n"
            f"Ekli dosya: {self.attached_file_path.name if self.attached_file_path else 'yok'}\n"
            f"Bugun: {today}\n"
            f"Yarin: {tomorrow}\n"
            f"V3 beyin: {self.brain.status_summary()}\n"
            f"Hafiza: {self.brain.memory_summary()}\n"
            "Mevcut yetenekler: Windows uygulama ac/kapat, Spotify/YouTube arama, Defender tarama, "
            "zamanli kapatma, cockpit/mini mod, yerel planlayici, site cevirisi, Kick/Opera, guvenli Riot modu.\n"
            "Guvenlik kuralı: silme, mesaj gonderme, takvim silme, terminal komutu, ozel kisi arama ve hassas islemlerde onay iste."
        )

    def run_powershell_value(self, command, timeout=6):
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except Exception as exc:
            return f"okunamadi: {exc}"
        output = (completed.stdout or completed.stderr or "").strip()
        return " ".join(output.split())[:180] if output else "okunamadi"

    def diagnostics_summary(self):
        cpu = self.run_powershell_value("(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty LoadPercentage)")
        ram = self.run_powershell_value(
            "$os=Get-CimInstance Win32_OperatingSystem; "
            "$used=[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,1); "
            "$total=[math]::Round($os.TotalVisibleMemorySize/1MB,1); "
            "'{0}/{1} GB' -f $used,$total"
        )
        disk = self.run_powershell_value(
            "$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\"; "
            "$free=[math]::Round($d.FreeSpace/1GB,1); $total=[math]::Round($d.Size/1GB,1); "
            "'C: {0}/{1} GB bos' -f $free,$total"
        )
        python_count = self.run_powershell_value("(Get-Process python -ErrorAction SilentlyContinue | Measure-Object).Count")
        memory_total = sum(
            len(self.brain.memory.get(section, []))
            for section in ["user_facts", "project_notes", "goals", "routines", "feedback_rules", "lessons"]
        )
        command_report = self.brain.command_report()
        defender = self.defender_status_summary()
        return (
            f"JARVIS teshis raporu: CPU %{cpu}. RAM {ram}. Disk {disk}. "
            f"Python sureci: {python_count}. Hafiza kaydi: {memory_total}. "
            f"Defender: {defender} Komut ogrenme: {command_report}"
        )

    # ESKİ → güncellendi
    def chat_completion_text(self, messages, preferred_model=None, fallback_model=None, max_tokens=None, temperature=None):
        if not self.client:
            raise RuntimeError("OpenAI API anahtari bulunamadi.")

        primary = preferred_model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        fallback = fallback_model if fallback_model is not None else os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4.1-mini")
        models = []
        for model in [primary, fallback]:
            if model and model not in models:
                models.append(model)

        last_error = None
        for model in models:
            try:
                kwargs = {"model": model, "messages": messages}
                if max_tokens is not None:
                    kwargs["max_tokens"] = int(max_tokens)
                if temperature is not None:
                    kwargs["temperature"] = float(temperature)
                response = self.client.chat.completions.create(**kwargs)
                self.last_model_used = model
                self.log.emit(f"> MODEL: {model}")
                self.log_event("MODEL", model)
                if model != primary:
                    self.log.emit(f"> API: {primary} yerine {model} kullanildi.")
                return response.choices[0].message.content
            except Exception as exc:
                last_error = exc
                self.log.emit(f"> API: {model} yanit vermedi: {exc}")
                self.log_event("HATA", f"API {model} yanit vermedi: {exc}")

        raise last_error or RuntimeError("OpenAI yaniti alinamadi.")

    def is_complex_answer_request(self, text, decision=None):
        clean = norm(text)
        reason = norm(getattr(decision, "reason", "") if decision else "")
        has_decision = decision is not None
        confidence = float(getattr(decision, "confidence", 0.0) or 0.0)
        complex_markers = [
            "analiz",
            "strateji",
            "plan",
            "program",
            "gelisim",
            "karsilastir",
            "hesapla",
            "optimize",
            "detayli",
            "derin",
            "rapor",
            "mimari",
            "kod",
            "proje",
            "guvenlik",
            "performans",
            "alternatif",
            "taktik",
            "yorumla",
            "neden",
            "nasil gelistir",
            "ne eksik",
            "en iyi",
        ]
        reason_complex = any(marker in reason for marker in ["complex", "analysis", "strategy", "deep", "plan"])
        text_complex = len(clean.split()) >= 14 or any(marker in clean for marker in complex_markers)
        if not has_decision:
            return text_complex or reason_complex
        return confidence >= 0.90 and (text_complex or reason_complex)

    def answer_model_settings(self, text, decision=None):
        if self.is_complex_answer_request(text, decision):
            return {
                "model": JARVIS_COMPLEX_MODEL,
                "fallback": JARVIS_SIMPLE_MODEL,
                "max_tokens": JARVIS_COMPLEX_MAX_TOKENS,
                "temperature": JARVIS_COMPLEX_TEMPERATURE,
            }
        return {
            "model": JARVIS_SIMPLE_MODEL,
            "fallback": os.getenv("OPENAI_FALLBACK_MODEL", JARVIS_SIMPLE_MODEL),
            "max_tokens": JARVIS_SIMPLE_MAX_TOKENS,
            "temperature": JARVIS_SIMPLE_TEMPERATURE,
        }

    def answer_with_selected_model(self, text, decision=None):
        settings = self.answer_model_settings(text, decision)
        messages = [
            {"role": "system", "content": self.jarvis_system_prompt()},
            {"role": "system", "content": self.manager_context()},
        ]
        if decision and decision.reply:
            messages.append({
                "role": "system",
                "content": (
                    f"V3 karar: answer, guven %{int((decision.confidence or 0) * 100)}, "
                    f"sebep: {decision.reason or 'yok'}. Ilk taslak: {decision.reply}"
                ),
            })
        messages.extend(self.conversation_history[-6:])
        messages.append({"role": "user", "content": text})
        try:
            return self.chat_completion_text(
                messages,
                preferred_model=settings["model"],
                fallback_model=settings["fallback"],
                max_tokens=settings["max_tokens"],
                temperature=settings["temperature"],
            )
        except Exception as exc:
            self.log.emit(f"> MODEL HATASI: {exc}")
            return decision.reply if decision and decision.reply else None

    def vision_completion_text(self, prompt, image_data_url):
        if not self.client:
            raise RuntimeError("OpenAI API anahtari bulunamadi.")

        primary = os.getenv("OPENAI_VISION_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.5"))
        fallback = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4.1-mini")
        privacy_filter = (
            "Ekranda su bilgileri ASLA tekrar etme:\n"
            "- API anahtarlari (sk-, Bearer ile baslayanlar)\n"
            "- Sifreler\n"
            "- Kredi karti numaralari\n"
            "- Discord ozel mesajlari\n"
            "- .env icerigi\n\n"
            "Bu bilgileri gordugunde sadece sunu de: 'Efendim, hassas bilgi tespit ettim, atladim.'"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "Sen JARVIS'in izinli ekran yorumlama modusun. Ekrandaki yazilari ve durumu Turkce yorumla. "
                    "Sifre, API anahtari, ozel mesaj, kimlik bilgisi gibi hassas verileri aynen tekrar etme. "
                    "Oyun/site/ayar ekrani gorursen sadece guvenli taktik, uyari ve sonraki adim oner. "
                    "Kisa, net ve uygulanabilir cevap ver.\n\n"
                    + privacy_filter
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ]
        return self.chat_completion_text(messages, preferred_model=primary if primary else fallback)

    def set_attached_file(self, file_path):
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return "Dosya bulunamadi."
        self.attached_file_path = path
        self.last_action_summary = f"Dosya eklendi: {path.name}"
        return f"Dosya eklendi: {path.name}. 'Bu dosyayi tara ve ozetini anlat' diyebilirsin."

    def clear_attached_file(self):
        self.attached_file_path = None
        return "Ekli dosya kaldirildi."

    def image_file_data_url(self, path):
        ext = path.suffix.lower()
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }.get(ext, "image/png")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def extract_pdf_text(self, path, max_pages=20):
        pdf_reader = None
        try:
            from pypdf import PdfReader
            pdf_reader = PdfReader(str(path))
        except Exception:
            try:
                from PyPDF2 import PdfReader
                pdf_reader = PdfReader(str(path))
            except Exception as exc:
                raise RuntimeError(
                    "PDF okumak icin pypdf gerekli. Terminalde su komutu calistir: .\\.venv\\Scripts\\python.exe -m pip install pypdf"
                ) from exc

        pages = []
        page_count = min(len(pdf_reader.pages), max_pages)
        for index in range(page_count):
            page = pdf_reader.pages[index]
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                pages.append(f"[Sayfa {index + 1}]\n{text.strip()}")
        return "\n\n".join(pages).strip()

    def extract_docx_text(self, path):
        try:
            with zipfile.ZipFile(path) as docx:
                xml_data = docx.read("word/document.xml")
        except Exception as exc:
            raise RuntimeError(f"DOCX okunamadi: {exc}") from exc
        root = ET.fromstring(xml_data)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            joined = "".join(texts).strip()
            if joined:
                paragraphs.append(joined)
        return "\n".join(paragraphs)

    def read_text_file(self, path):
        for encoding in ["utf-8", "utf-8-sig", "cp1254", "latin-1"]:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(errors="ignore")

    def extract_file_text(self, path):
        ext = path.suffix.lower()
        if ext == ".pdf":
            return self.extract_pdf_text(path)
        if ext == ".docx":
            return self.extract_docx_text(path)
        if ext in [".txt", ".md", ".csv", ".json", ".log", ".py", ".js", ".ts", ".html", ".htm", ".xml", ".yaml", ".yml"]:
            return self.read_text_file(path)
        raise RuntimeError("Bu dosya turunu metin olarak okuyamiyorum. PDF, DOCX, TXT/MD/CSV/JSON veya gorsel dosya sec.")

    def summarize_file_text(self, path, text, instruction):
        if not self.client:
            return "Dosya ozetlemek icin OpenAI API anahtari gerekli."
        text = " ".join(str(text or "").split())
        if not text:
            return "Dosyadan okunabilir metin cikaramadim. PDF tarama goruntuyse OCR modulu gerekir."
        excerpt = text[:28000]
        messages = [
            {
                "role": "system",
                "content": (
                    "Sen JARVIS dosya analiz modusun. Turkce, net ve uygulanabilir cevap ver. "
                    "Dosyanin turunu, ana konusunu, onemli maddeleri, risk/eksik bilgileri ve kullanicinin ne yapmasi gerektigini ozetle. "
                    "Gereksiz uzun yazma; once kisa sonuc, sonra maddeler."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Dosya adi: {path.name}\n"
                    f"Kullanici istegi: {instruction or 'Dosyayi tara ve ozetini anlat.'}\n\n"
                    f"Okunan metin:\n{excerpt}"
                ),
            },
        ]
        return self.chat_completion_text(messages)

    def analyze_attached_file(self, instruction=""):
        path = self.attached_file_path
        if not path:
            return "Once DOSYA butonundan bir PDF, fotograf, ekran goruntusu veya metin dosyasi eklemelisin."
        if not path.exists():
            self.attached_file_path = None
            return "Ekli dosya artik bulunamiyor. DOSYA butonundan tekrar sec."

        ext = path.suffix.lower()
        image_exts = [".png", ".jpg", ".jpeg", ".webp", ".bmp"]
        try:
            if ext in image_exts:
                prompt = (
                    f"Dosya adi: {path.name}\n"
                    f"Kullanici istegi: {instruction or 'Bu gorseli tara ve ozetini anlat.'}\n"
                    "Gorseldeki yazilari OCR gibi oku, ana konuyu anlat, gorev/uyari/talimat varsa net maddelerle soyle."
                )
                return self.vision_completion_text(prompt, self.image_file_data_url(path))
            text = self.extract_file_text(path)
            return self.summarize_file_text(path, text, instruction)
        except Exception as exc:
            return f"Dosya analiz edilemedi: {exc}"

    def capture_screen_data_url(self):
        if ImageGrab is not None:
            try:
                screenshot = ImageGrab.grab()
                buffer = io.BytesIO()
                screenshot.save(buffer, format="PNG")
                encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
                return "data:image/png;base64," + encoded
            except Exception as exc:
                if not self.screen_capture_warning_shown:
                    self.screen_capture_warning_shown = True
                    self.log.emit(f"> EKRAN: ImageGrab calismadi, PyAutoGUI deneniyor: {exc}")

        try:
            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            return "data:image/png;base64," + encoded
        except Exception as exc:
            if not self.screen_capture_warning_shown:
                self.screen_capture_warning_shown = True
                self.log.emit(f"> EKRAN: PyAutoGUI ekran yakalama calismadi, PyQt yedegi deneniyor: {exc}")

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("Ekran yakalanamadi: aktif ekran bulunamadi.")

        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            raise RuntimeError("Ekran yakalanamadi: PyQt bos goruntu dondurdu.")

        qt_buffer = QBuffer()
        qt_buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(qt_buffer, "PNG")
        encoded = base64.b64encode(bytes(qt_buffer.data())).decode("ascii")
        qt_buffer.close()
        return "data:image/png;base64," + encoded

    def capture_screen(self):
        data_url = self.capture_screen_data_url()
        if "," in data_url:
            return data_url.split(",", 1)[1]
        return data_url

    def ask_with_screen(self, user_text):
        if not self.client:
            return "Ekran analizi icin OpenAI API anahtari gerekli."
        img_base64 = self.capture_screen()
        response = self.client.chat.completions.create(
            model=os.getenv("JARVIS_SCREEN_MODEL", "gpt-4o"),
            max_tokens=1000,
            messages=[
                {
                    "role": "system",
                    "content": "Sen Jarvis'sin. Ekran görüntüsünü analiz et ve kullanıcıya Türkçe kısa cevap ver.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                        },
                        {
                            "type": "text",
                            "text": user_text,
                        },
                    ],
                },
            ],
        )
        self.last_model_used = os.getenv("JARVIS_SCREEN_MODEL", "gpt-4o")
        self.log.emit(f"> MODEL: {self.last_model_used}")
        self.log_event("EKRAN", "Ekran goruntusu alindi ve analiz edildi")
        return response.choices[0].message.content

    def is_one_shot_screen_command(self, text):
        text = norm(text)
        triggers = [
            "ekrana bak",
            "ekranima bak",
            "ekrani analiz et",
            "ekranimi analiz et",
            "ekran analiz et",
            "ne goruyorsun",
            "ekranda ne var",
            "bunu oku",
            "su an ne acik",
            "şu an ne açık",
        ]
        return any(trigger in text for trigger in triggers)

    # ESKI -> guncellendi
    def ask_with_screen(self, user_text):
        if not self.client:
            return "Ekran analizi icin OpenAI API anahtari gerekli."
        try:
            img_base64 = self.capture_screen()
            screen_model = os.getenv("JARVIS_SCREEN_MODEL", "gpt-4o")
            privacy_filter = (
                "Ekranda su bilgileri ASLA tekrar etme:\n"
                "- API anahtarlari (sk-, Bearer ile baslayanlar)\n"
                "- Sifreler\n"
                "- Kredi karti numaralari\n"
                "- Discord ozel mesajlari\n"
                "- .env icerigi\n\n"
                "Bu bilgileri gordugunde sadece sunu de: 'Efendim, hassas bilgi tespit ettim, atladim.'"
            )
            response = self.client.chat.completions.create(
                model=screen_model,
                max_tokens=1000,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Sen Jarvis'sin. Ekran goruntusunu analiz et ve kullaniciya Turkce kisa cevap ver.\n\n"
                            + privacy_filter
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                            },
                            {
                                "type": "text",
                                "text": user_text,
                            },
                        ],
                    },
                ],
            )
            self.last_model_used = screen_model
            self.log.emit(f"> MODEL: {self.last_model_used}")
            self.log_event("MODEL", self.last_model_used)
            self.log_event("EKRAN", "Ekran goruntusu alindi ve analiz edildi")
            answer = response.choices[0].message.content
            try:
                self.brain.add_screen_history(answer)
            except Exception:
                pass
            return answer
        except Exception as exc:
            self.log_event("HATA", f"Ekran analizi hatasi: {exc}")
            return f"Ekrani analiz edemedim efendim: {exc}"

    def analyze_screen_once(self, reason="canli ekran modu"):
        image_data_url = self.capture_screen_data_url()
        prompt = (
            f"Neden izliyorsun: {reason}\n"
            "Ekranda ne oldugunu, okunabilen ana yazilari ve kullanicinin dikkat etmesi gereken seyi ozetle. "
            "Eger oyun ekraniysa taktik ver; web sitesiyse guvenilirlik/sonraki adim oner; ayar ekraniysa hangi ayarin onemli oldugunu soyle. "
            "Onemli bir sey yoksa bunu kisaca belirt."
        )
        answer = self.vision_completion_text(prompt, image_data_url)
        try:
            self.brain.add_screen_history(answer)
        except Exception:
            pass
        return answer

    def parse_duration_seconds(self, text, default_seconds=300):
        text = norm(text)
        match = re.search(r"(\d{1,3})\s*(saniye|sn)", text)
        if match:
            return max(10, min(3600, int(match.group(1))))
        match = re.search(r"(\d{1,3})\s*(dakika|dk|dakka)", text)
        if match:
            return max(30, min(7200, int(match.group(1)) * 60))
        return default_seconds

    def start_screen_watch(self, duration_seconds=600, interval_seconds=None, reason="kullanicinin izin verdigi canli ekran izleme"):
        if not self.client:
            return "Canli ekran modu icin OpenAI API anahtari gerekli."
        if self.screen_watch_thread and self.screen_watch_thread.is_alive():
            return "Canli ekran modu zaten acik. Kapatmak icin 'ekran izlemeyi durdur' diyebilirsin."

        interval_seconds = interval_seconds or int(os.getenv("SCREEN_WATCH_INTERVAL_SECONDS", "30"))
        interval_seconds = max(10, min(180, int(interval_seconds)))
        duration_seconds = max(30, min(7200, int(duration_seconds)))
        self.screen_watch_stop.clear()
        self.screen_watch_until = time.time() + duration_seconds

        def loop():
            self.log.emit("> EKRAN: Canli ekran modu basladi. Goruntuler kaydedilmiyor, anlik analiz ediliyor.")
            while not self.screen_watch_stop.is_set() and time.time() < self.screen_watch_until:
                try:
                    self.status.emit("EKRAN IZLENIYOR")
                    answer = self.analyze_screen_once(reason)
                    self.last_action_summary = "Canli ekran analizi yaptim."
                    self.log.emit(f"> EKRAN: {answer}")
                    if answer:
                        self.speak(answer)
                except Exception as exc:
                    self.log.emit(f"> EKRAN HATASI: {exc}")
                remaining = max(0, self.screen_watch_until - time.time())
                wait_time = min(interval_seconds, remaining)
                if wait_time <= 0:
                    break
                self.screen_watch_stop.wait(wait_time)
            self.status.emit("AKTIF")
            self.log.emit("> EKRAN: Canli ekran modu kapandi.")

        self.screen_watch_thread = threading.Thread(target=loop, daemon=True)
        self.screen_watch_thread.start()
        return f"Canli ekran modu {self.format_delay(duration_seconds)} boyunca acildi. Her {interval_seconds} saniyede bir yorumlayacagim."

    def stop_screen_watch(self):
        if not self.screen_watch_thread or not self.screen_watch_thread.is_alive():
            return "Canli ekran modu zaten kapali."
        self.screen_watch_stop.set()
        return "Canli ekran modu kapatiliyor."

    def web_research(self, query):
        if not self.client:
            return "Web arastirma icin OpenAI API anahtari gerekli."

        query = " ".join(str(query or "").split()).strip()
        if not query:
            return "Neyi arastiracagimi anlayamadim."

        today = dt.datetime.now().strftime("%Y-%m-%d")
        prompt = (
            f"Bugunun tarihi: {today}. Kullanici su konuyu arastirmami istedi: {query}\n"
            "Resmi sayfa, wiki/yardim sayfasi ve guvenilir kaynaklari karsilastir. "
            "Guncel/aktif bilgi ile eski veya supheli bilgiyi ayir. "
            "Roblox kodu, fiyat, surum, haber veya uygulama bilgisi varsa uydurma; kaynak ve tarih belirt. "
            "Cevabi Turkce ver.\n"
            "Cevap formati cok onemli: once tek satirlik KISA CEVAP ver. "
            "Oyun icindeyse en fazla 5 kisa maddeyle rota, NPC/quest adi, gerekli gorev ve dikkat notunu soyle. "
            "Detayli ansiklopedi yazma; kullanici oyun oynarken hizli taktik istiyor. "
            "Sonunda en fazla 4 kaynak URL'si ve kontrol tarihini ekle."
        )

        primary_model = os.getenv("OPENAI_RESEARCH_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.5"))
        fallback_model = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4.1-mini")
        models = []
        for candidate in [primary_model, fallback_model]:
            if candidate and candidate not in models:
                models.append(candidate)
        last_error = None
        for model in models:
            for tool_type in ["web_search", "web_search_preview"]:
                try:
                    response = self.client.responses.create(
                        model=model,
                        tools=[{"type": tool_type}],
                        tool_choice="auto",
                        include=["web_search_call.action.sources"],
                        input=prompt,
                    )
                    if model != primary_model:
                        self.log.emit(f"> WEB: {primary_model} yerine {model} kullanildi.")
                    output_text = getattr(response, "output_text", None)
                    if output_text:
                        return output_text
                    if hasattr(response, "model_dump"):
                        data = response.model_dump()
                        texts = []
                        for item in data.get("output", []):
                            for content in item.get("content", []):
                                if content.get("type") in ["output_text", "text"] and content.get("text"):
                                    texts.append(content["text"])
                        if texts:
                            return "\n".join(texts)
                    return "Web arastirma tamamlandi ama okunabilir bir yanit cikmadi."
                except Exception as exc:
                    last_error = exc

        return (
            "Web arastirma modu calisamadi. Uydurma cevap vermiyorum. "
            f"Hata: {last_error}"
        )

    def prepare_tts_text(self, text):
        spoken = str(text or "").strip()
        if len(spoken) <= 900:
            return spoken

        stop_markers = [
            "\n---",
            "\n## Kullanilan kaynak",
            "\n## Kaynak",
            "\nKullanilan kaynak",
            "\nKaynak URL",
        ]
        for marker in stop_markers:
            index = spoken.lower().find(marker.lower())
            if index > 0:
                spoken = spoken[:index].strip()
                break

        cleaned_lines = []
        for line in spoken.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("http") or "http://" in line or "https://" in line:
                continue
            line = re.sub(r"[*_`>#\[\]()]", "", line).strip()
            if line:
                cleaned_lines.append(line)
            if len(cleaned_lines) >= 7:
                break

        short = " ".join(cleaned_lines).strip()
        if len(short) > 850:
            short = short[:850].rsplit(" ", 1)[0].strip()
        return short + " Detaylari ekrana yazdim."

    async def speak_async(self, text, force=False):
        self.log.emit(f"> JARVIS: {text}")
        if self.quiet_mode and not force:
            return

        if edge_tts is None or pygame is None:
            return

        spoken_text = self.prepare_tts_text(text)
        if not spoken_text:
            return

        self.speech_stop_requested = False
        filename = BASE_DIR / f"voice_{uuid.uuid4().hex}.mp3"
        self.speaking.emit(True)
        try:
            communicate = edge_tts.Communicate(spoken_text, VOICE, rate=VOICE_RATE, pitch=VOICE_PITCH)
            await communicate.save(str(filename))

            pygame.mixer.init()
            pygame.mixer.music.load(str(filename))
            pygame.mixer.music.set_volume(self.voice_volume)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if self.speech_stop_requested:
                    pygame.mixer.music.stop()
                    break
                await asyncio.sleep(0.1)

            pygame.mixer.music.unload()
            pygame.mixer.quit()
        finally:
            self.speech_stop_requested = False
            self.speaking.emit(False)
            try:
                filename.unlink()
            except OSError:
                pass

    def stop_speaking(self):
        self.speech_stop_requested = True
        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception as exc:
            self.log.emit(f"> SES: Susturma denenemedi: {exc}")
        self.speaking.emit(False)

    def speak(self, text, force=False):
        with self.speak_lock:
            try:
                asyncio.run(self.speak_async(text, force=force))
            except Exception as exc:
                self.log.emit(f"> SES HATASI: {exc}")

    def lower_own_voice(self):
        self.quiet_mode = False
        self.voice_volume = max(0.05, self.voice_volume - 0.18)
        percent = int(self.voice_volume * 100)
        self.speak(f"Kendi sesimi kıstım efendim. Şu an yüzde {percent}.", force=True)

    def raise_own_voice(self):
        self.quiet_mode = False
        self.voice_volume = min(1.0, self.voice_volume + 0.18)
        percent = int(self.voice_volume * 100)
        self.speak(f"Kendi sesimi yükselttim efendim. Şu an yüzde {percent}.", force=True)

    def set_own_voice_percent(self, percent):
        self.quiet_mode = False
        percent = max(5, min(100, int(percent)))
        self.voice_volume = percent / 100
        self.speak(f"Kendi sesimi yüzde {percent} olarak ayarladım efendim.", force=True)

    def enter_quiet_mode(self):
        self.quiet_mode = True
        self.speak("Tamam, sessiz bekleme moduna geçiyorum.", force=True)

    def leave_quiet_mode(self):
        self.quiet_mode = False
        self.speak("Sesli moda döndüm efendim.", force=True)

    def set_pending(self, action):
        self.pending_action = action
        risk_messages = {
            "shutdown": "bilgisayari kapatma",
            "restart": "bilgisayari yeniden baslatma",
            "clear_memory": "JARVIS hafizasini silme",
            "screen_watch": "ekrani izinli izleme",
            "defender_scan": "uzun surebilecek guvenlik taramasi",
            "incognito_edge": "gizli sekme acma",
            "edge_research": "tarayicida arastirma acma",
            "public_search": "herkese acik web aramasi acma",
            "discord_message": "Discord uzerinden mesaj gonderme",
            "lol_pick": "oyun ekrani otomasyonu",
            "game_mode_csgo": "oyun modu: uygulama kapatma ve CS baslatma",
        }
        risk = risk_messages.get(str(action.get("type")), "hassas islem")
        self.speak(f"Bu islem {risk} kategorisinde. Onayliyorsan BUNU YAP de, vazgecmek icin IPTAL ET de.")
        return
        self.speak("Bu işlem için geçici yetki istiyorum. Onaylıyorsan BUNU YAP de.")

    def execute_pending(self):
        if not self.pending_action:
            self.speak("Bekleyen bir işlem yok efendim.")
            return "DONE"

        action = self.pending_action
        self.pending_action = None
        self.last_action_summary = f"Onaylanan islem calistirildi: {action.get('type', 'bilinmeyen')}"

        if action["type"] == "shutdown":
            delay_seconds = int(action.get("delay_seconds", 10))
            warning_seconds = int(action.get("warning_seconds", 30))
            os.system(f"shutdown /s /t {delay_seconds}")
            self.schedule_shutdown_warning(delay_seconds, warning_seconds)
            self.speak(f"Bilgisayar {self.format_delay(delay_seconds)} sonra kapatilacak.")
            return "DONE"
            os.system("shutdown /s /t 10")
            self.speak("Bilgisayar 10 saniye içinde kapatılıyor.")
            return "DONE"

        if action["type"] == "restart":
            os.system("shutdown /r /t 10")
            self.speak("Bilgisayar 10 saniye içinde yeniden başlatılıyor.")
            return "DONE"

        if action["type"] == "clear_memory":
            self.brain.clear_memory()
            self.speak("JARVIS hafizasi temizlendi efendim.")
            return "DONE"

        if action["type"] == "screen_watch":
            result = self.start_screen_watch(
                duration_seconds=action.get("duration_seconds", 600),
                interval_seconds=action.get("interval_seconds"),
                reason=action.get("reason", "kullanicinin izin verdigi canli ekran izleme"),
            )
            self.speak(result)
            return "DONE"

        if action["type"] == "incognito_edge":
            url = action.get("url")
            if url:
                os.system(f'start msedge -inprivate "{url}"')
                self.speak("Edge gizli sekmede istediğin arama açıldı.")
            else:
                os.system("start msedge -inprivate")
                self.speak("Edge gizli sekme açıldı.")
            return "DONE"

        if action["type"] == "edge_research":
            query = action["query"]
            video_query = action.get("video_query") or query
            self.last_research_subject = action.get("subject") or query
            self.last_action_summary = f"Edge gizli sekmede arastirma actim: {query}"
            google_url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
            youtube_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(video_query)

            os.system(f'start msedge -inprivate "{youtube_url}"')
            time.sleep(0.7)
            os.system(f'start msedge -inprivate "{google_url}"')

            if action.get("answer"):
                try:
                    answer = self.ask_gpt_manager(action["answer"])
                except Exception as exc:
                    answer = f"Bilgi özetini hazırlayamadım: {exc}"
                self.speak(answer)
            else:
                self.speak("Edge gizli sekmede YouTube ve Google aramaları açıldı.")
            return "DONE"

        if action["type"] == "public_search":
            query = action["query"]
            self.last_research_subject = query
            self.last_action_summary = f"Herkese acik arama sayfalarini actim: {query}"
            urls = self.make_search_urls(
                query,
                include_social=action.get("social", False),
                include_images=action.get("images", False),
                include_youtube=action.get("youtube", False),
            )
            self.open_edge_private_urls(urls)
            self.speak("Herkese acik arama sayfalarini actim efendim.")
            return "DONE"

        if action["type"] == "edge_site":
            os.system(f'start msedge "{action["url"]}"')
            self.speak("Edge üzerinden site açıldı.")
            return "DONE"

        if action["type"] == "defender_scan":
            result = self.start_defender_scan(action.get("scan", "quick"))
            self.speak(result)
            return "DONE"

        if action["type"] == "game_mode_csgo":
            result = self.run_game_mode_csgo()
            self.speak(result)
            return "DONE"

        if action["type"] == "discord_message":
            result = self.discord_send_message(action.get("kisi_adi", ""), action.get("mesaj", ""))
            self.speak(result)
            return "DONE"

        if action["type"] == "lol_pick":
            champion = action["champion"]
            delay = action["delay"]
            self.speak(f"{delay} saniye sonra {champion} seçmeyi deneyeceğim.")

            def task():
                time.sleep(delay)
                coords = self.load_coords()

                if "lol_search" not in coords or "lol_lock" not in coords:
                    self.speak("LoL koordinatları kayıtlı değil. Önce arama kutusu ve kilitle butonunu öğretmelisin.")
                    return

                pyautogui.click(coords["lol_search"]["x"], coords["lol_search"]["y"])
                time.sleep(0.3)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.write(champion, interval=0.03)
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(0.5)
                pyautogui.click(coords["lol_lock"]["x"], coords["lol_lock"]["y"])
                self.speak(f"{champion} seçme işlemi denendi.")

            threading.Thread(target=task, daemon=True).start()
            return "DONE"

        return None

    def remember_mouse_position(self, name):
        x, y = pyautogui.position()
        coords = self.load_coords()
        coords[name] = {"x": x, "y": y}
        self.save_coords(coords)
        self.speak(f"{name} konumunu kaydettim efendim.")

    def iter_process_names(self):
        if psutil is not None:
            try:
                for proc in psutil.process_iter(["name"]):
                    name = (proc.info.get("name") or "").lower()
                    if name:
                        yield name
                return
            except Exception as exc:
                self.log.emit(f"> OYUN MODU: psutil okunamadi, tasklist deneniyor: {exc}")

        try:
            completed = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in completed.stdout.splitlines():
                name = line.split(",", 1)[0].strip().strip('"').lower()
                if name:
                    yield name
        except Exception as exc:
            self.log.emit(f"> OYUN MODU: process listesi okunamadi: {exc}")

    def process_running(self, process_names):
        wanted = {name.lower() for name in process_names}
        return any(name in wanted for name in self.iter_process_names())

    def safe_close_processes(self, process_names):
        closed = []
        skipped = []
        failed = []
        wanted = {name.lower() for name in process_names}
        current_pid = os.getpid()
        python_names = {"python.exe", "python3.exe", "pythonw.exe"}

        if psutil is not None:
            try:
                for proc in psutil.process_iter(["pid", "name"]):
                    info = proc.info or {}
                    pid = info.get("pid")
                    name = (info.get("name") or "").lower()
                    if not name or name not in wanted:
                        continue
                    if pid == current_pid or name in python_names:
                        skipped.append(f"{name}:{pid}")
                        continue
                    if name in self.GAME_PROTECTED_PROCESSES or "jarvis" in name:
                        skipped.append(name)
                        continue
                    try:
                        proc.terminate()
                        closed.append(name)
                    except Exception:
                        failed.append(name)
                return closed, skipped, failed
            except Exception as exc:
                self.log.emit(f"> OYUN MODU: psutil kapatma hatasi, taskkill deneniyor: {exc}")
                self.log_event("HATA", f"psutil process kapatma hatasi: {exc}")

        for process_name in process_names:
            normalized = process_name.lower()
            if normalized in self.GAME_PROTECTED_PROCESSES or normalized in python_names or "jarvis" in normalized:
                skipped.append(process_name)
                continue
            try:
                completed = subprocess.run(
                    ["taskkill", "/im", process_name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                output = (completed.stdout + completed.stderr).lower()
                if completed.returncode == 0:
                    closed.append(process_name)
                elif "not found" not in output and "bulunamad" not in output:
                    failed.append(process_name)
            except Exception:
                failed.append(process_name)
        return closed, skipped, failed

    def start_riot_client(self):
        riot_path = Path(r"C:\Riot Games\Riot Client\RiotClientServices.exe")
        if riot_path.exists():
            os.system(f'start "" "{riot_path}"')
        else:
            os.system('start "" "C:\\Riot Games\\Riot Client\\RiotClientServices.exe"')

    def start_discord(self):
        os.system("start discord")

    def type_turkish(self, text):
        text = str(text or "")
        if pyperclip is not None:
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.2)
            return
        pyautogui.write(text, interval=0.03)

    def is_process_running_contains(self, needle):
        needle = norm(needle)
        if psutil is None:
            return False
        try:
            for proc in psutil.process_iter(["name"]):
                name = str(proc.info.get("name") or "")
                if needle in norm(name):
                    return True
        except Exception:
            return False
        return False

    def focus_discord_window(self):
        if gw is None:
            return False
        try:
            discord_windows = [
                window for window in gw.getAllWindows()
                if "discord" in str(window.title or "").lower()
            ]
            if discord_windows:
                discord_windows[0].activate()
                time.sleep(0.5)
                return True
        except Exception as exc:
            self.log.emit(f"> DISCORD: pencere one alinamadi: {exc}")
        return False

    def parse_discord_message_command(self, text):
        raw = " ".join(str(text or "").split()).strip()
        if not raw:
            return None
        match = re.match(r"^(?:jarvis\s+)?(?:discordda|discord da|dc de|dcde)\s+(.+)$", raw, flags=re.I)
        if not match:
            return None

        body = match.group(1).strip()
        lowered = body.lower()
        for suffix in [" mesaj at", " yaz", " at"]:
            if lowered.endswith(suffix):
                body = body[: -len(suffix)].strip()
                break

        if not body:
            return None

        split_match = re.match(r"^(.+?)\s+(?:e|ye|ya)\s+(.+)$", body, flags=re.I)
        if split_match:
            kisi_adi = split_match.group(1).strip(" '\"")
            mesaj = split_match.group(2).strip()
        else:
            parts = body.split(maxsplit=1)
            if len(parts) < 2:
                return None
            kisi_adi = parts[0].strip(" '\"")
            mesaj = parts[1].strip()
            lowered_name = kisi_adi.lower()
            if len(kisi_adi) > 2 and lowered_name.endswith(("ye", "ya")):
                kisi_adi = kisi_adi[:-2]
            elif len(kisi_adi) > 2 and lowered_name.endswith("e"):
                kisi_adi = kisi_adi[:-1]

        if not kisi_adi or not mesaj:
            return None
        return {"kisi_adi": kisi_adi.strip(), "mesaj": mesaj.strip()}

    def discord_send_message(self, kisi_adi, mesaj):
        kisi_adi = str(kisi_adi or "").strip()
        mesaj = str(mesaj or "").strip()
        if not kisi_adi or not mesaj:
            return "Efendim, Discord mesaji icin kisi adi veya mesaj eksik."
        if psutil is None:
            return "Efendim, Discord kontrolu icin psutil gerekli."
        if pyperclip is None:
            return "Efendim, Turkce karakterli Discord mesaji icin pyperclip gerekli. requirements.txt guncellendi."
        if gw is None:
            return "Efendim, Discord penceresini one almak icin pygetwindow gerekli. requirements.txt guncellendi."

        discord_running = self.is_process_running_contains("discord")
        if not discord_running:
            self.start_discord()
            time.sleep(4)

        self.focus_discord_window()
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.5)
        self.type_turkish(kisi_adi)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(0.7)
        self.type_turkish(mesaj)
        time.sleep(0.3)
        pyautogui.press("enter")

        self.last_action_summary = f"Discord mesaji gonderildi: {kisi_adi}"
        self.log_event("DISCORD", f"{kisi_adi} e mesaj gonderildi")
        return f"Efendim, {kisi_adi}'e mesaj gonderildi."

    def start_spotify(self):
        os.system("start spotify")

    def open_site_in_opera(self, url):
        candidates = [
            Path(r"C:\Users\Public\Opera\opera.exe"),
            Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Opera" / "opera.exe",
            Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Opera GX" / "launcher.exe",
        ]
        command = None
        for candidate in candidates:
            if candidate.exists():
                command = [str(candidate), url]
                break
        if command is None:
            command = ["opera", url]
        try:
            subprocess.Popen(command)
        except Exception:
            os.system(f'start opera "{url}"')
        self.last_action_summary = f"Opera ile site acildi: {url}"
        return "Opera'da site acildi efendim."

    def opera_url_from_command(self, text):
        clean = norm(text)
        if any(phrase in clean for phrase in ["migrosa gir", "migros a gir", "migros ac", "migrosa ac"]):
            return "https://www.migros.com.tr"
        if any(phrase in clean for phrase in ["hepsiburadaya gir", "hepsiburada ya gir", "hepsiburada ac", "hepsiburadaya ac"]):
            return "https://www.hepsiburada.com"

        if "opera" not in clean and "operada" not in clean and "operadan" not in clean:
            return None

        query = clean
        for phrase in ["operada", "operadan", "opera", "ac", "aç", "gir", "siteye", "sitesine"]:
            query = query.replace(phrase, " ")
        query = " ".join(query.split()).strip()
        if not query:
            return None
        if query.startswith("http://") or query.startswith("https://"):
            return query
        known_sites = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "kick": "https://kick.com",
            "twitch": "https://www.twitch.tv",
            "migros": "https://www.migros.com.tr",
            "hepsiburada": "https://www.hepsiburada.com",
            "trendyol": "https://www.trendyol.com",
        }
        if query in known_sites:
            return known_sites[query]
        if "." in query and " " not in query:
            return "https://" + query
        return "https://www.google.com/search?q=" + urllib.parse.quote(query)

    def open_default_browser(self):
        try:
            webbrowser.open("https://www.google.com")
        except Exception as exc:
            self.log.emit(f"> OYUN MODU: tarayici acilamadi: {exc}")

    def start_game_mode_watcher(self, profile, target_names):
        self.game_mode_watch_stop.set()
        if self.game_mode_watch_thread and self.game_mode_watch_thread.is_alive():
            self.game_mode_watch_thread.join(timeout=0.2)
        self.game_mode_watch_stop = threading.Event()
        self.game_mode_target_seen = False

        def watcher():
            while not self.game_mode_watch_stop.is_set():
                active = self.process_running(target_names)
                if active:
                    self.game_mode_target_seen = True
                elif self.game_mode_target_seen:
                    self.exit_game_mode(auto=True, profile=profile)
                    break
                time.sleep(5)

        self.game_mode_watch_thread = threading.Thread(target=watcher, daemon=True)
        self.game_mode_watch_thread.start()

    def enter_game_mode(self, profile):
        profile = profile.upper()
        close_targets = list(self.GAME_SAFE_KILL)
        if profile == "VALORANT":
            close_targets.extend(self.GAME_VALORANT_EXTRA_KILL)

        closed, skipped, failed = self.safe_close_processes(close_targets)
        if profile == "LOL":
            self.start_spotify()
        self.start_riot_client()
        self.start_discord()

        self.mode = "OYUN"
        self.current_game_profile = profile
        self.pyautogui_enabled = False
        self.quiet_mode = False
        self.status.emit("OYUN MODU")
        self.last_action_summary = f"Oyun modu {profile} baslatildi."
        self.log_event("OYUN", f"{profile} modu aktif")

        if profile == "LOL":
            self.start_game_mode_watcher("LOL", ["LeagueClient.exe"])
            message = "Oyun moduna geçildi efendim."
        else:
            self.start_game_mode_watcher("VALORANT", ["VALORANT.exe", "VALORANT-Win64-Shipping.exe"])
            message = "Valorant moduna geçildi efendim."

        if skipped:
            self.log.emit("> OYUN MODU: Korunan processlere dokunulmadi: " + ", ".join(skipped))
        if failed:
            self.log.emit("> OYUN MODU: Kapatilamayanlar: " + ", ".join(failed))
        if closed:
            self.log.emit("> OYUN MODU: Kapatilanlar: " + ", ".join(closed))

        self.speak(message, force=True)
        self.quiet_mode = True
        return "DONE"

    def exit_game_mode(self, auto=False, profile=None):
        profile = (profile or self.current_game_profile or "OYUN").upper()
        self.game_mode_watch_stop.set()
        self.mode = "AKTIF"
        self.current_game_profile = None
        self.pyautogui_enabled = True
        self.quiet_mode = False
        self.status.emit("AKTIF")
        self.open_default_browser()
        message = "Valorant bitti, aktif moda dönüldü efendim." if profile == "VALORANT" else "Oyun bitti, aktif moda dönüldü efendim."
        if not auto:
            message = "Oyun modundan çıkıldı, aktif moda dönüldü efendim."
        self.log_event("OYUN", f"{profile} modu kapandi; aktif moda donuldu")
        self.speak(message, force=True)
        return "DONE"

    def handle_game_mode_command(self, text):
        text = norm(text)
        if self.mode != "OYUN":
            return None

        if any(phrase in text for phrase in ["oyun modundan cik", "oyun modunu kapat", "aktif moda don", "normal moda don"]):
            return self.exit_game_mode(auto=False)

        if any(phrase in text for phrase in ["discord kapat", "discordu kapat"]):
            os.system("taskkill /im discord.exe")
            self.speak("Discord kapatildi efendim.", force=True)
            self.quiet_mode = True
            return "DONE"

        if any(phrase in text for phrase in ["discord ac", "discordu ac", "discord baslat"]):
            self.start_discord()
            self.speak("Discord acildi efendim.", force=True)
            self.quiet_mode = True
            return "DONE"

        if "ses yukselt" in text:
            pyautogui.press("volumeup", presses=5)
            self.speak("Ses yukseltildi efendim.", force=True)
            self.quiet_mode = True
            return "DONE"

        if "ses azalt" in text:
            pyautogui.press("volumedown", presses=5)
            self.speak("Ses azaltildi efendim.", force=True)
            self.quiet_mode = True
            return "DONE"

        if "sesi kapat" in text:
            pyautogui.press("volumemute")
            self.speak("Ses kapatildi efendim.", force=True)
            self.quiet_mode = True
            return "DONE"

        self.log.emit("> OYUN MODU: Kisitli modda komut yok sayildi.")
        return "DONE"

    def run_game_mode_csgo(self):
        keep_note = "Discord ve Steam korunuyor."
        close_targets = [
            ("chrome.exe", "Chrome"),
            ("msedge.exe", "Edge"),
            ("opera.exe", "Opera"),
            ("opera_gx.exe", "Opera GX"),
            ("firefox.exe", "Firefox"),
            ("brave.exe", "Brave"),
            ("Spotify.exe", "Spotify"),
            ("EpicGamesLauncher.exe", "Epic Games"),
            ("RiotClientServices.exe", "Riot Client"),
            ("RiotClientUx.exe", "Riot Client UI"),
            ("Battle.net.exe", "Battle.net"),
            ("XboxPcApp.exe", "Xbox"),
        ]
        closed = []
        failed = []
        for process_name, label in close_targets:
            try:
                completed = subprocess.run(
                    ["taskkill", "/im", process_name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                output = (completed.stdout + completed.stderr).lower()
                if completed.returncode == 0:
                    closed.append(label)
                elif "not found" not in output and "bulunamad" not in output:
                    failed.append(label)
            except Exception:
                failed.append(label)

        os.system('start "" "steam://rungameid/730"')
        self.last_action_summary = "OYUN MODU CSGO calisti: dikkat dagitan uygulamalar kapatildi, Steam AppID 730 acildi."
        closed_text = ", ".join(closed) if closed else "kapatilacak hedef bulunmadi"
        failed_text = f" Kapanmayanlar: {', '.join(failed)}." if failed else ""
        return (
            f"OYUN MODU CSGO baslatildi. {keep_note} Kapatilanlar: {closed_text}. "
            f"Counter-Strike Steam uzerinden aciliyor.{failed_text} "
            "Not: Kaydedilmemis dosya tutabilecek editorleri zorla kapatmadim."
        )

    def should_answer_with_ai(self, text):
        text = norm(text)

        explicit_browser_or_app_task = (
            ("edge" in text and ("gizli" in text or "inprivate" in text))
            or ("kick" in text and any(word in text for word in ["ac", "bak", "yayinda", "gir"]))
            or ("spotify" in text and any(word in text for word in ["ac", "cal", "baslat", "dinle", "ara"]))
            or ("spotfy" in text and any(word in text for word in ["ac", "cal", "baslat", "dinle", "ara"]))
            or ("youtube" in text and any(word in text for word in ["ac", "izle", "cal", "ara", "kapat"]))
        )

        direct_question_markers = QUESTION_MARKERS + ["kim oldugunu"]

        if not is_question_like(text):
            return False

        if explicit_browser_or_app_task and not any(
            marker in text
            for marker in [
                "nasil",
                "nedir",
                "neden",
                "ne yapabilirim",
                "ne yapmaliyim",
                "kimdir",
                "indirebilirim",
                "indirmek icin",
                "gonderebilirim",
            ]
        ):
            return False

        return True

    def should_use_v3_router(self, text):
        if not self.v3_enabled:
            return False
        text = norm(text)
        exact_local = {
            "bunu yap",
            "onayla",
            "onayliyorum",
            "onay veriyorum",
            "tamam onayla",
            "iptal et",
            "vazgec",
            "kapat",
            "kapan",
            "cik",
            "dur",
            "kendini kapat",
        }
        if text in exact_local:
            return False

        words = text.split()
        if len(words) >= 4:
            return True

        intent_markers = [
            "nasil",
            "neden",
            "nedir",
            "kimdir",
            "arastir",
            "anlat",
            "acikla",
            "plan",
            "hatirlat",
            "spotify",
            "spotfy",
            "youtube",
            "discord",
            "dc de",
            "kick",
            "cevir",
            "virus",
            "defender",
            "v3",
            "zeka",
            "hafiza",
        ]
        return any(marker in text for marker in intent_markers)

    def route_with_v3(self, text):
        if not self.should_use_v3_router(text):
            return None

        decision = self.brain.decide(
            text,
            runtime_context=self.manager_context(),
            history=self.conversation_history,
        )
        self.log.emit(
            f"> V3: {decision.action} %{int(decision.confidence * 100)}"
            + (f" - {decision.reason}" if decision.reason else "")
        )

        if decision.reason in ["missing_api_key", "model_error"]:
            self.log.emit("> V3: Eski JARVIS akisi deneniyor.")
            return None

        if decision.action == "local_command":
            command = decision.normalized_command or text
            if decision.reason in ["screen_watch_request", "game_screen_task_request", "local_screen_watch"] and any(
                phrase in norm(text)
                for phrase in ["izin veriyorum", "onay veriyorum", "onayliyorum", "bakmana izin", "bakmana onay"]
            ):
                normalized_command = norm(command)
                if not any(phrase in normalized_command for phrase in ["izin veriyorum", "onay veriyorum", "onayliyorum", "bakmana izin", "bakmana onay"]):
                    command = f"{command} onay veriyorum"
            if norm(command) != norm(text):
                self.log.emit(f"> V3 KOMUT: {command}")
            result = self.computer_command(command)
            if result:
                return result
            if decision.reply:
                return decision.reply
            return None

        if decision.action == "plan_add":
            payload = decision.payload
            scope = payload.get("scope") or "bugun"
            title = payload.get("title") or ""
            time_text = str(payload.get("time") or "").strip()
            hour = ""
            minute = "00"
            match = re.match(r"^(\d{1,2})(?::(\d{2}))?$", time_text)
            if match:
                hour = match.group(1)
                minute = match.group(2) or "00"
            result = self.add_plan_item(scope, title, hour, minute)
            self.ui_command.emit(f"plan:{scope}")
            return result

        if decision.action == "open_panel":
            panel = str(decision.payload.get("panel") or "HOME").upper()
            if panel == "PLANNER":
                self.ui_command.emit("plan:bugun")
            elif panel in ["HOME", "DASHBOARD", "SETTINGS"]:
                self.ui_command.emit(f"tab:{panel}")
            else:
                self.ui_command.emit("tab:HOME")
            return decision.reply or "Paneli actim efendim."

        if decision.action == "remember":
            payload = decision.payload
            section = payload.get("section") or "user_facts"
            allowed_sections = ["user_facts", "project_notes", "goals", "routines", "feedback_rules", "command_mistakes", "lessons"]
            if section not in allowed_sections:
                section = "user_facts"
            memory_text = payload.get("text") or decision.reply
            if self.brain.add_memory(section, memory_text):
                return decision.reply or "Bunu hafizama aldim."
            return decision.reply or "Bunu zaten hatirliyorum."

        # ESKİ → güncellendi
        if decision.action == "answer":
            return self.answer_with_selected_model(text, decision) or decision.reply or None

        if decision.action in ["clarify", "unsafe_refusal"]:
            return decision.reply or None

        return None

    def computer_command(self, text):
        original_text = text
        text = norm(text)

        if text in ["kapat", "kapan", "cik", "dur", "kendini kapat"]:
            return "EXIT"

        if any(phrase in text for phrase in ["v3 kapat", "akilli mod kapat", "beyin modunu kapat"]):
            self.v3_enabled = False
            return "JARVIS v3 akilli yonlendirme kapatildi. Eski komut motoruyla devam ediyorum."

        if any(phrase in text for phrase in ["v3 ac", "akilli mod ac", "beyin modunu ac"]):
            self.v3_enabled = True
            return "JARVIS v3 akilli yonlendirme acildi."

        if any(phrase in text for phrase in ["v3 durum", "akilli mod durum", "beyin durum", "jarvis v3 durum"]):
            state = "acik" if self.v3_enabled else "kapali"
            return f"Akilli yonlendirme {state}. {self.brain.status_summary()}"

        if any(phrase in text for phrase in ["kendini kontrol et", "jarvis teshis yap", "teshis raporu", "diagnostics", "sistem teshisi"]):
            return self.diagnostics_summary()

        if any(phrase in text for phrase in ["komut ogrenme raporu", "komut gecmisinden ne ogrendin", "son hatalarin ne", "hata raporu"]):
            return self.brain.command_report()

        if any(phrase in text for phrase in ["guvenlik kurallarin ne", "riskli islemler neler", "onay sistemini anlat"]):
            return (
                "Guvenlik katmanim: kapatma, yeniden baslatma, tam Defender taramasi, ekran izleme, gizli sekme, "
                "ozel kisi arama, hesap/oyun riski ve silme gibi islemlerde onay isterim. "
                "Düşük riskli bilgi sorularinda onay istemem; emin degilsem once kisa soru sorarim."
            )

        if any(phrase in text for phrase in ["oyun modu lol", "lol oyun modu", "league of legends oyun modu", "oyun modu league"]):
            return self.enter_game_mode("LOL")

        if any(phrase in text for phrase in ["oyun modu valorant", "valorant oyun modu", "valo oyun modu", "oyun modu valo"]):
            return self.enter_game_mode("VALORANT")

        if any(phrase in text for phrase in ["oyun modu csgo", "oyun modu cs go", "csgo oyun modu", "cs go oyun modu", "oyun modu counter"]):
            if any(phrase in text for phrase in ["onayliyorum", "onayli", "onay veriyorum", "bunu yap"]):
                return self.run_game_mode_csgo()
            self.set_pending({"type": "game_mode_csgo"})
            return "DONE"

        discord_message = self.parse_discord_message_command(original_text)
        if discord_message:
            self.set_pending({
                "type": "discord_message",
                "kisi_adi": discord_message["kisi_adi"],
                "mesaj": discord_message["mesaj"],
            })
            return f"Efendim, Discord'da {discord_message['kisi_adi']} kisisine su mesaj hazirlandi: {discord_message['mesaj']}. Onayliyorsan BUNU YAP de."

        if any(phrase in text for phrase in ["dosya ekle", "dosya sec", "pdf ekle", "fotograf ekle", "ss ekle"]):
            self.ui_command.emit("select_file")
            return "Dosya secme penceresini actim. Dosyayi sectikten sonra 'bu dosyayi tara ve ozetini anlat' diyebilirsin."

        if any(phrase in text for phrase in ["ekli dosya ne", "hangi dosya ekli", "dosya durum"]):
            if self.attached_file_path:
                return f"Ekli dosya: {self.attached_file_path.name}"
            return "Su an ekli dosya yok. DOSYA butonundan dosya ekleyebilirsin."

        if any(phrase in text for phrase in ["dosyayi kaldir", "ekli dosyayi kaldir", "dosyayi unut"]):
            return self.clear_attached_file()

        file_analyze_requested = (
            any(word in text for word in ["dosya", "pdf", "fotograf", "foto", "resim", "ss", "ekran goruntusu", "belge"])
            and any(word in text for word in ["tara", "analiz", "ozet", "oku", "coz", "anlat", "incele"])
        )
        if file_analyze_requested:
            return self.analyze_attached_file(text)

        # ESKI -> guncellendi
        if self.is_one_shot_screen_command(text):
            self.status.emit("EKRAN ANALIZ")
            return self.ask_with_screen(text)

        if any(phrase in text for phrase in ["neleri hatirliyorsun", "hafiza durumu", "hafizanda ne var", "beni ne kadar taniyorsun"]):
            sections = {
                "Kullanici": self.brain.memory.get("user_facts", [])[-8:],
                "Hedef": self.brain.memory.get("goals", [])[-6:],
                "Rutin": self.brain.memory.get("routines", [])[-6:],
                "Proje": self.brain.memory.get("project_notes", [])[-6:],
                "Cevap kurali": self.brain.memory.get("feedback_rules", [])[-6:],
                "Komut hatasi": self.brain.memory.get("command_mistakes", [])[-4:],
                "Ders": self.brain.memory.get("lessons", [])[-4:],
            }
            if not any(sections.values()):
                return "Hafizam su an bos. 'Bunu hatirla: ...' dersen kaydetmeye baslarim."
            parts = []
            for label, items in sections.items():
                if items:
                    parts.append(label + ": " + " | ".join(items))
            return "Hatirladiklarim: " + " // ".join(parts)

        feedback_rules = [
            ("bu cevap iyiydi", "Kullanici bu cevap tarzini begendi; benzer durumda ayni netlikte cevap ver."),
            ("iyi cevap", "Kullanici kisa ve net cevabi olumlu buldu."),
            ("cok uzun cevap verdin", "Daha kisa cevap ver; once sonucu soyle, ayrintiyi gerekirse ekle."),
            ("çok uzun cevap verdin", "Daha kisa cevap ver; once sonucu soyle, ayrintiyi gerekirse ekle."),
            ("kisa cevap ver", "Cevaplari daha kisa tut."),
            ("beni yanlis anladin", "Emin degilsen islem yapmadan once kisa net soru sor."),
            ("beni yanlış anladın", "Emin degilsen islem yapmadan once kisa net soru sor."),
            ("yanlis anladin", "Emin degilsen islem yapmadan once kisa net soru sor."),
        ]
        for phrase, rule in feedback_rules:
            if phrase in text:
                if "yanlis" in phrase or "yanl" in phrase:
                    self.record_command_result(
                        self.last_meaningful_command or text,
                        "user_feedback",
                        "Kullanici komutun yanlis anlasildigini bildirdi.",
                        success=False,
                    )
                    self.brain.add_lesson("Kullanici 'beni yanlis anladin' derse ayni konuda islem yapmadan once netlestirme sorusu sor.")
                if self.brain.add_memory("feedback_rules", rule):
                    return "Geri bildirimi kaydettim. Sonraki cevaplarimi buna gore ayarlayacagim."
                return "Bu geri bildirimi zaten hatirliyorum."

        remember_match = re.search(r"(?:bunu|sunu)?\s*(?:hatirla|aklinda tut|hafizana al)[:\s]+(.+)", text)
        if remember_match:
            memory_text = remember_match.group(1).strip(" .,-")
            if any(word in memory_text for word in ["hedef", "amac", "basarmak", "istiyorum"]):
                section = "goals"
            elif any(word in memory_text for word in ["her gun", "hergun", "sabah", "aksam", "rutin"]):
                section = "routines"
            elif any(word in memory_text for word in ["proje", "jarvis", "kod", "uygulama"]):
                section = "project_notes"
            else:
                section = "user_facts"
            if self.brain.add_memory(section, memory_text):
                return "Bunu hafizama aldim."
            return "Bunu zaten hatirliyorum."

        if any(phrase in text for phrase in ["hafizayi temizle", "hafizami temizle", "beni unut"]):
            self.set_pending({"type": "clear_memory"})
            return "DONE"

        delete_match = re.search(r"hafiza(?:dan|mda)?\s+(.+?)\s+(?:sil|kaldir|unut)", text)
        if delete_match:
            fragment = delete_match.group(1).strip(" .,-")
            removed = self.brain.delete_memory_containing(fragment)
            if removed:
                return f"Hafizadan {removed} kaydi sildim."
            return "Hafizada bu ifadeyi iceren kayit bulamadim."

        if any(phrase in text for phrase in ["ekran izlemeyi durdur", "canli ekran modunu kapat", "ekrana bakmayi birak", "ekrani izlemeyi durdur"]):
            return self.stop_screen_watch()

        game_screen_task_requested = (
            any(phrase in text for phrase in ["oyundaki gorev", "gorevi anlay", "gorev yazisi", "quest yazisi", "questi anlay"])
            and any(word in text for word in ["bak", "oku", "anla", "soyle", "analiz"])
        )

        screen_watch_requested = (
            any(phrase in text for phrase in ["ekranima", "ekranimi", "ekrani", "ekrana", "ekran", "canli ekran", "tanrima", "tanrimi"])
            and any(word in text for word in ["bak", "izle", "yorumla", "takip", "analiz", "oku", "gorev", "quest"])
        ) or game_screen_task_requested
        if screen_watch_requested:
            duration_seconds = self.parse_duration_seconds(text, default_seconds=600)
            interval_seconds = int(os.getenv("SCREEN_WATCH_INTERVAL_SECONDS", "30"))
            reason = text.replace("tanrima", "ekranima").replace("tanrimi", "ekranimi")
            if any(phrase in text for phrase in ["izin veriyorum", "onay veriyorum", "onayliyorum", "bakmana izin", "bakmana onay"]):
                return self.start_screen_watch(
                    duration_seconds=duration_seconds,
                    interval_seconds=interval_seconds,
                    reason=reason,
                )
            self.set_pending({
                "type": "screen_watch",
                "duration_seconds": duration_seconds,
                "interval_seconds": interval_seconds,
                "reason": reason,
            })
            return "DONE"

        # ESKI -> guncellendi
        opera_url = self.opera_url_from_command(text)
        if opera_url:
            return self.open_site_in_opera(opera_url)

        private_context = any(word in text for word in ["personel", "calisan", "kadin", "adam", "dhl", "sosyal medya", "instagram", "tiktok"])
        identity_hunt = any(
            phrase in text
            for phrase in [
                "kim oldugunu",
                "kimdir",
                "hesabini bul",
                "sosyal medya hesabini",
                "tanimak istiyorum",
                "internette ara",
                "bulabilir misin",
                "tum internette ara",
            ]
        ) and any(word in text for word in ["arastir", "ara", "bul", "sun", "anlat", "kim"])
        if private_context and identity_hunt:
            return (
                "Bunu ozel bir kisiyi bulma veya takip etme seviyesinde yapamam. "
                "Ama istersen saygili tanisma mesaji, guvenli iletisim plani veya halka acik resmi bilgi kontrolu hazirlayabilirim."
            )

        game_update_research_requested = (
            any(word in text for word in ["roblox", "sailor piece", "oyun"])
            and any(word in text for word in ["guncelleme", "update", "quest", "quester", "kod", "nerede", "yerini"])
            and any(word in text for word in ["kontrol", "arastir", "bak", "soyle"])
        )

        web_research_requested = game_update_research_requested or any(
            phrase in text
            for phrase in [
                "resmi sayfadan",
                "wikiden",
                "wiki den",
                "web arastir",
                "internetten dogrula",
                "guncel bilgi",
                "kaynakli arastir",
                "kaynaklarla arastir",
            ]
        ) and any(word in text for word in ["arastir", "kontrol", "bak", "dogrula", "kod", "surum", "fiyat", "haber", "wiki"])
        if web_research_requested:
            query = text
            for phrase in [
                "jarvis",
                "resmi sayfadan",
                "wikiden",
                "wiki den",
                "web arastir",
                "internetten dogrula",
                "guncel bilgi",
                "kaynakli arastir",
                "kaynaklarla arastir",
                "kontrol et",
                "bana",
                "soyle",
                "bak",
                "arastir",
            ]:
                query = query.replace(phrase, " ")
            query = " ".join(query.split()).strip()
            if not query:
                query = text
            self.status.emit("WEB ARASTIRMA")
            return self.web_research(query)

        if any(phrase in text for phrase in ["ne yaptin", "son islem ne", "az once ne yaptin", "neden actin", "neden actim bunlari", "bunlari neden actin"]):
            return f"Son islemim: {self.last_action_summary}"

        if any(phrase in text for phrase in ["acil susam acil", "jarvis nerdesin", "jarvis neredesin", "nerdesin jarvis", "neredesin jarvis", "nerdesin", "neredesin"]):
            self.ui_command.emit("show_panel")
            return "Buradayim efendim."

        if any(phrase in text for phrase in ["cockpit ac", "kokpit ac", "paneli buyut", "yan ekran modu", "buyuk panel"]):
            self.ui_command.emit("cockpit_on")
            return "Cockpit modu aciliyor efendim."

        if any(phrase in text for phrase in ["rehberi ac", "rehber panelini ac", "jarvis neler yapabilirsin", "jarvis ne yapabilirsin"]):
            self.ui_command.emit("tab:HOME")
            return "Rehber panelini actim efendim. Buradan neler yapabilecegini gorebilirsin."

        if any(phrase in text for phrase in ["sistem panelini ac", "sistem durumunu ac", "dashboard ac", "durum panelini ac"]):
            self.ui_command.emit("tab:DASHBOARD")
            return "Sistem panelini actim efendim."

        plan_add = re.search(
            r"\b(bugun|yarin)\b.*?(?:saat\s+)?(\d{1,2})(?:[:.](\d{2}))?\s+(.*?)(?:\s+diye)?\s+(?:ekle|hatirlat|kaydet)$",
            text,
        )
        if plan_add:
            scope, hour, minute, title = plan_add.groups()
            title = re.sub(r"\b(planima|planina|plana|gorev|is|bana)\b", " ", title)
            title = " ".join(title.split())
            result = self.add_plan_item(scope, title, hour, minute or "00")
            self.ui_command.emit(f"plan:{scope}")
            return result

        plan_add_no_time = re.search(
            r"\b(bugun|yarin)\b\s+(.*?)(?:\s+diye)?\s+(?:plana ekle|planima ekle|planina ekle|ekle|kaydet)$",
            text,
        )
        if plan_add_no_time:
            scope, title = plan_add_no_time.groups()
            title = re.sub(r"\b(planima|planina|plana|gorev|is|bana)\b", " ", title)
            title = " ".join(title.split())
            result = self.add_plan_item(scope, title)
            self.ui_command.emit(f"plan:{scope}")
            return result

        if any(phrase in text for phrase in ["yarinin planlarini ac", "yarin planlarini ac", "yarinki planlari ac", "yarin ne yapacagim", "yarin ne yapacam"]):
            self.ui_command.emit("plan:yarin")
            return "Yarinin plan panelini actim efendim. Saat saat planlarini buradan yonetecegiz."

        if any(phrase in text for phrase in ["bugunun planlarini ac", "bugun planlarini ac", "bugun ne yapacagim", "plan panelini ac"]):
            self.ui_command.emit("plan:bugun")
            return "Bugunun plan panelini actim efendim."

        if any(phrase in text for phrase in ["bugunku planimi oku", "bugun planimi oku", "bugunun planini oku"]):
            self.ui_command.emit("plan:bugun")
            return self.format_plan_summary("bugun")

        if any(phrase in text for phrase in ["yarinki planimi oku", "yarin planimi oku", "yarinin planini oku"]):
            self.ui_command.emit("plan:yarin")
            return self.format_plan_summary("yarin")

        if any(phrase in text for phrase in ["ayar panelini ac", "ayarlari ac", "jarvis ayarlari"]):
            self.ui_command.emit("tab:SETTINGS")
            return "Ayar panelini actim efendim."

        if self.should_answer_with_ai(text):
            return None

        if any(phrase in text for phrase in ["cockpit kapat", "kokpit kapat", "kucuk panele don", "normal panele don"]):
            self.ui_command.emit("cockpit_off")
            return "Normal panele donuyorum efendim."

        if any(phrase in text for phrase in ["mini moda gec", "kucul", "alta al", "paneli kucult"]):
            self.ui_command.emit("mini_on")
            return "Mini moda geciyorum efendim."

        if any(phrase in text for phrase in ["performans modu", "performans modunu ac", "drop azalt", "kasmasin"]):
            self.ui_command.emit("performance_on")
            return "Performans modu acildi efendim. Animasyon yuku azaltiliyor."

        if any(phrase in text for phrase in ["gorsel modu", "animasyon modu", "performans modunu kapat"]):
            self.ui_command.emit("performance_off")
            return "Gorsel mod acildi efendim. Animasyonlar biraz daha yogun calisacak."

        if text in ["wake kapan", "wake kapat", "wake dur", "hey jarvis kapan", "hey jarvis kapat"]:
            self.ui_command.emit("wake_off")
            return "Wake modu kapatildi efendim. Tekrar acmak icin yazili olarak wake ac demelisin."

        if text in ["wake ac", "wake aç", "wake baslat", "wake açıl", "hey jarvis ac"]:
            self.ui_command.emit("wake_on")
            return "Wake modu acildi efendim."

        if any(phrase in text for phrase in ["sus ve bekle", "sessiz bekle", "simdilik sus", "konusma bekle"]):
            self.enter_quiet_mode()
            return "DONE"

        if any(phrase in text for phrase in ["tekrar konus", "sesli devam", "konusabilirsin", "artik konus"]):
            self.leave_quiet_mode()
            return "DONE"

        own_voice_words = ["sesini", "kendi sesini", "senin sesin", "jarvis sesi", "jarvisin sesi"]
        if any(word in text for word in own_voice_words):
            percent_match = re.search(r"(?:%|yuzde\s*)(\d{1,3})|(\d{1,3})\s*(?:%|yuzde)", text)
            if percent_match:
                percent = percent_match.group(1) or percent_match.group(2)
                self.set_own_voice_percent(percent)
                return "DONE"

        if any(word in text for word in own_voice_words) and any(word in text for word in ["kis", "azalt", "dusur", "minimum", "min", "en dusuk"]):
            self.lower_own_voice()
            return "DONE"

        if any(word in text for word in own_voice_words) and any(word in text for word in ["ac", "yukselt", "artir"]):
            self.raise_own_voice()
            return "DONE"

        if any(phrase in text for phrase in ["baslangicta acil", "otomatik acil", "windows acilinca acil", "bilgisayar acilinca acil"]):
            return "Bunu ekledim efendim: klasördeki enable_startup.bat dosyasını bir kez çalıştırman yeterli."

        if self.pending_action and self.pending_action.get("type") == "shutdown" and "son" in text and "saniye" in text:
            warning_seconds = self.parse_delay_seconds(text, default_seconds=30)
            self.pending_action["warning_seconds"] = warning_seconds
            self.speak(f"Tamam. Kapanmaya son {warning_seconds} saniye kala iptal secenegini hatirlatacagim.")
            return "DONE"

        if text in ["bunu yap", "onayla", "onayliyorum", "onay veriyorum", "tamam onayla", "devam etsin"]:
            return self.execute_pending()

        if text in ["iptal et", "iptal ediyorum", "vazgec", "kapatmayi iptal et", "kapanmayi iptal et"]:
            if self.pending_action:
                self.pending_action = None
                return "Bekleyen islem iptal edildi."
            os.system("shutdown /a")
            return "Zamanlanmis kapatma iptal edildi."

        translate_requested = any(word in text for word in ["cevir", "turkce", "turkceye", "turkce yap", "tercume"])
        if translate_requested:
            if any(word in text for word in ["secili", "secilen", "bu yazi", "yaziyi", "metni"]):
                return self.translate_selected_text()

            if any(word in text for word in ["site", "sayfa", "sayfayi", "web", "ekran"]):
                return self.translate_current_site()

        lol_related = (
            "lol" in text
            or "league of legends" in text
            or "opgg" in text
            or "u gg" in text
            or "ugg" in text
            or any(word in text for word in ["hazirla", "run", "rune", "runes", "build", "sampiyon", "hero"])
        )

        if lol_related:
            settings = self.load_lol_settings()

            if any(phrase in text for phrase in ["lol modu kapat", "lol yardim modu kapat"]):
                settings["enabled"] = False
                self.save_lol_settings(settings)
                return "LoL yardim modu kapatildi."

            if any(phrase in text for phrase in ["lol modu ac", "lol yardim modu", "lol yardimci modu"]):
                settings["enabled"] = True
                role = self.detect_lol_role(text)
                champion = self.extract_lol_champion(text)
                if role:
                    settings["role"] = role
                if champion:
                    settings["favorite_champion"] = champion
                self.save_lol_settings(settings)
                return "LoL yardim modu acildi. Sampiyon hazirlamak icin 'yasuo mid hazirla' veya 'zed runlerini ac' diyebilirsin."

            if any(phrase in text for phrase in ["favori sampiyon kaydet", "favori hero kaydet", "sampiyon kaydet", "hero kaydet"]):
                champion = self.extract_lol_champion(text)
                role = self.detect_lol_role(text) or settings.get("role") or "mid"
                if not champion:
                    return "Kaydedecegim sampiyonu anlayamadim. Ornek: favori sampiyon kaydet yasuo mid."
                settings["favorite_champion"] = champion
                settings["role"] = role
                settings["enabled"] = True
                self.save_lol_settings(settings)
                return f"Favori LoL hazirligin kaydedildi: {champion} {role}."

            if any(word in text for word in ["hazirla", "run", "rune", "runes", "build", "opgg", "ugg"]):
                champion = self.extract_lol_champion(text) or settings.get("favorite_champion")
                role = self.detect_lol_role(text) or settings.get("role") or "mid"
                return self.open_lol_helper(champion=champion, role=role)

            if any(word in text for word in ["kabul", "kilitle", "pick", "sec"]):
                return "Bunu otomatik yapmiyorum efendim; hesap riski olabilir. Rün/build sayfasini acarim, kabul ve kilitlemeyi sen manuel yapmalisin."

        if any(word in text for word in ["virus", "antivirus", "defender", "tehdit", "zararli"]):
            if any(phrase in text for phrase in ["windows guvenligi ac", "defender ac", "antivirus ac"]):
                os.system("start windowsdefender:")
                return "Windows Guvenligi acildi."

            if any(word in text for word in ["tam", "komple", "ayrintili", "detayli"]):
                self.set_pending({"type": "defender_scan", "scan": "full"})
                return "DONE"

            if any(word in text for word in ["tara", "tarama", "kontrol", "varmi", "var mi", "hizli"]):
                return self.start_defender_scan("quick")

            return self.defender_status_summary()

        if "ayni seyi" in text and "icin yap" in text:
            subject = self.extract_subject_after_markers(text, ["ayni seyi"])
            if not subject:
                return "Kimin icin yapacagimi anlayamadim efendim."
            self.set_pending({
                "type": "public_search",
                "query": subject,
                "social": False,
                "images": True,
                "youtube": True,
            })
            return "DONE"

        if any(phrase in text for phrase in ["gorselini ac", "resmini ac"]):
            subject = self.extract_subject_after_markers(text, ["gorselini ac", "resmini ac"])
            if not subject:
                subject = self.last_research_subject
            if not subject:
                return "Kimin gorselini acacagimi anlayamadim efendim."
            self.set_pending({
                "type": "public_search",
                "query": subject,
                "social": False,
                "images": True,
                "youtube": False,
            })
            return "DONE"

        if any(site in text for site in ["instagram", "tiktok", "yotube", "youtube", "sosyal ag", "sosyal medya"]):
            if any(word in text for word in ["ara", "bul", "arayip", "arastir"]):
                subject = self.extract_subject_after_markers(text, ["bul", "ara", "sosyal aglarda", "sosyal medya"])
                if not subject:
                    subject = self.last_research_subject
                if not subject:
                    return "Kimi sosyal aglarda arayacagimi anlayamadim efendim."
                self.set_pending({
                    "type": "public_search",
                    "query": subject,
                    "social": True,
                    "images": True,
                    "youtube": True,
                })
                return "DONE"

        if "kapatmayi iptal et" in text or "yeniden baslatmayi iptal et" in text:
            os.system("shutdown /a")
            return "Kapatma veya yeniden başlatma iptal edildi."

        if "bilgisayari kapat" in text or "pc kapat" in text:
            delay_seconds = self.parse_delay_seconds(text, default_seconds=10)
            self.set_pending({
                "type": "shutdown",
                "delay_seconds": delay_seconds,
                "warning_seconds": 30 if delay_seconds > 45 else 0,
            })
            return "DONE"

        if "yeniden baslat" in text or "restart" in text:
            self.set_pending({"type": "restart"})
            return "DONE"

        if "edge" in text and ("gizli" in text or "inprivate" in text) and any(word in text for word in ["ara", "arastir", "video", "videosu", "ac"]):
            query = clean_query(text)
            query = query.replace("edge", "").replace("gizli", "").replace("sekmede", "").replace("sekme", "")
            query = query.replace("oraya", "").replace("gir", "").replace("acik", "").replace("açık", "")
            query = " ".join(query.split()).strip()

            if not query:
                self.set_pending({"type": "incognito_edge"})
                return "DONE"

            video_query = query
            if "hayat gecmisini" in query:
                video_query = query.split("hayat gecmisini")[0].strip()
            if "hayatini" in query:
                video_query = query.split("hayatini")[0].strip()

            answer_prompt = None
            if any(word in text for word in ["anlat", "ozetle", "arastir"]):
                answer_prompt = (
                    f"{query} konusu hakkında Türkçe, kısa ve anlaşılır bir özet ver. "
                    "Kesin bilmediğin güncel detayları kesinmiş gibi söyleme."
                )

            self.set_pending({
                "type": "edge_research",
                "query": query or text,
                "video_query": video_query or query or text,
                "answer": answer_prompt,
                "subject": query or text,
            })
            return "DONE"

        if "edge" in text and ("gizli" in text or "inprivate" in text):
            self.set_pending({"type": "incognito_edge"})
            return "DONE"

        if "edge" in text and "ac" in text:
            os.system("start msedge")
            return "Edge açıldı."

        if "google" in text and ("ac" in text or "gir" in text):
            webbrowser.open("https://google.com")
            return "Google açıldı."

        if "kick" in text or "kick.com" in text:
            channel = self.extract_kick_channel(text)
            fullscreen = "tam ekran" in text or "fullscreen" in text
            side_screen = "yan ekran" in text or "yan ekrana" in text
            check_live = "yayinda" in text or "yayindaysa" in text
            browser = "opera" if "opera" in text or "operadan" in text else "default"

            if "giris" in text or "login" in text:
                channel = None

            return self.open_kick(
                channel=channel,
                browser=browser,
                fullscreen=fullscreen,
                side_screen=side_screen,
                check_live=check_live,
            )

        spotify_requested = "spotify" in text or "spotfy" in text or (
            "uygulama" in text and any(word in text for word in ["sarki", "sarkiyi", "sarkisini", "muzik", "cal", "baslat"])
        )

        if spotify_requested:
            if "kapat" in text:
                os.system("taskkill /f /im Spotify.exe")
                return "Spotify kapatildi."

            query = self.spotify_query_from_text(text)
            fallback_to_last = (
                not query
                and self.last_spotify_query
                and any(word in text for word in ["google", "buldun", "degil", "sarkiyi"])
            )
            if fallback_to_last:
                query = self.last_spotify_query
            if not query and self.last_spotify_query and any(word in text for word in ["tekrar", "onu", "bunu", "devam"]):
                query = self.last_spotify_query

            if query:
                autoplay = any(word in text for word in ["baslat", "cal", "dinle", "ac"])
                return self.open_spotify_app_search(query, autoplay=autoplay)

            os.system("start spotify")
            return "Spotify acildi."

        if "youtube" in text and "kapat" in text:
            pyautogui.hotkey("ctrl", "w")
            return "YouTube sekmesi kapatıldı."

        if "youtube" in text:
            query = clean_query(text)
            if query:
                url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
                webbrowser.open(url)
                return f"YouTube'da {query} aranıyor."
            webbrowser.open("https://youtube.com")
            return "YouTube açıldı."

        if "spotify" in text and "kapat" in text:
            os.system("taskkill /f /im Spotify.exe")
            return "Spotify kapatıldı."

        if "spotify" in text:
            query = clean_query(text)
            if query:
                webbrowser.open("https://open.spotify.com/search/" + urllib.parse.quote(query))
                return f"Spotify'da {query} aranıyor."
            os.system("start spotify")
            return "Spotify açıldı."

        if any(word in text for word in ["muzik", "sarki", "video", "cal", "mozart", "radyo"]):
            query = clean_query(text)
            if query:
                url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
                webbrowser.open(url)
                return f"YouTube'da {query} aranıyor."

        app_commands = {
            "opera": ("start opera", "Opera açıldı.", "taskkill /f /im opera.exe", "Opera kapatıldı."),
            "chrome": ("start chrome", "Chrome açıldı.", "taskkill /f /im chrome.exe", "Chrome kapatıldı."),
            "discord": ("start discord", "Discord açıldı.", None, None),
        }
        for app_name, (open_cmd, open_msg, close_cmd, close_msg) in app_commands.items():
            if app_name in text and "kapat" in text and close_cmd:
                os.system(close_cmd)
                return close_msg
            if app_name in text and ("ac" in text or "baslat" in text):
                os.system(open_cmd)
                return open_msg

        if any(game in text for game in ["riot", "valorant", "league of legends"]):
            if "ac" in text or "baslat" in text:
                os.system('start "" "C:\\Riot Games\\Riot Client\\RiotClientServices.exe"')
                return "Riot Client açıldı."

        if "yeni sekme" in text or "sekme ac" in text:
            pyautogui.hotkey("ctrl", "t")
            return "Yeni sekme açıldı."

        if "sekme kapat" in text:
            pyautogui.hotkey("ctrl", "w")
            return "Sekme kapatıldı."

        if "ses yukselt" in text:
            pyautogui.press("volumeup", presses=5)
            return "Ses yükseltildi."

        if "ses azalt" in text:
            pyautogui.press("volumedown", presses=5)
            return "Ses azaltıldı."

        if "sesi kapat" in text:
            pyautogui.press("volumemute")
            return "Ses kapatıldı."

        if "masaustune don" in text:
            pyautogui.hotkey("win", "d")
            return "Masaüstüne dönüldü."

        if "baslat dedigimde buraya tikla" in text:
            self.remember_mouse_position("click_point")
            return "DONE"

        if text in ["baslat", "tikla", "sarkiyi baslat"]:
            coords = self.load_coords()
            point = coords.get("click_point")
            if not point:
                return "Kayıtlı nokta yok."
            pyautogui.click(point["x"], point["y"])
            return "Tıkladım efendim."

        if "lol arama kutusu burasi" in text:
            self.remember_mouse_position("lol_search")
            return "DONE"

        if "lol kilitle butonu burasi" in text:
            self.remember_mouse_position("lol_lock")
            return "DONE"

        if "saniye sonra" in text and ("sec" in text or "seç" in text):
            words = text.split()
            delay = next((int(word) for word in words if word.isdigit()), 10)
            champion = text.replace(str(delay), "")
            champion = champion.replace("saniye sonra", "").replace("sec", "").replace("seç", "").strip()

            if not champion:
                return "Hangi şampiyonu seçeceğimi anlayamadım."

            self.set_pending({"type": "lol_pick", "champion": champion, "delay": delay})
            return "DONE"

        return None

    def ask_gpt_manager(self, text):
        if not self.client:
            return "OpenAI API anahtari bulunamadi. .env dosyasina OPENAI_API_KEY eklemelisin."

        settings = self.answer_model_settings(text)
        messages = [
            {"role": "system", "content": self.jarvis_system_prompt()},
            {"role": "system", "content": self.manager_context()},
        ]
        messages.extend(self.conversation_history[-8:])
        messages.append({"role": "user", "content": text})

        return self.chat_completion_text(
            messages,
            preferred_model=settings["model"],
            fallback_model=settings["fallback"],
            max_tokens=settings["max_tokens"],
            temperature=settings["temperature"],
        )

    def ask_gpt(self, text):
        if not self.client:
            return "OpenAI API anahtari bulunamadi. .env dosyasina OPENAI_API_KEY eklemelisin."

        return self.chat_completion_text(
            [
                {
                    "role": "system",
                    "content": self.jarvis_system_prompt(),
                },
                {"role": "user", "content": text},
            ],
            preferred_model=JARVIS_SIMPLE_MODEL,
            fallback_model=os.getenv("OPENAI_FALLBACK_MODEL", JARVIS_SIMPLE_MODEL),
            max_tokens=JARVIS_SIMPLE_MAX_TOKENS,
            temperature=JARVIS_SIMPLE_TEMPERATURE,
        )

    def handle_command(self, text, speak_result=True):
        self.log.emit(f"> SEN: {text}")
        self.log.emit(f"> DUYDUGUM: {text}")
        self.status.emit("KOMUT ISLENIYOR")

        normalized_text = norm(text)
        self.last_model_used = None
        warnings = self.check_warnings(normalized_text)
        for warning in warnings:
            self.log.emit(f"> UYARI: {warning}")
            if speak_result:
                self.speak(warning, force=True)
        if self.mode == "OYUN":
            result = self.handle_game_mode_command(normalized_text)
            self.record_command_result(text, "game_mode_restricted", "Kisitli oyun modu komutu islendi.", success=True)
            self.status.emit("OYUN MODU")
            self.finished.emit(True)
            return result != "EXIT"

        repeat_phrases = [
            "deminki komutu yerine getir",
            "onceki komutu yerine getir",
            "son komutu yerine getir",
            "devam et",
            "kaldigin yerden devam et",
        ]

        if any(phrase in normalized_text for phrase in repeat_phrases):
            if self.pending_action:
                result = self.execute_pending()
                self.status.emit("AKTIF")
                self.finished.emit(True)
                return result != "EXIT"

            if self.last_meaningful_command:
                self.log.emit(f"> SISTEM: Onceki komut tekrar ediliyor: {self.last_meaningful_command}")
                text = self.last_meaningful_command
            else:
                self.speak("Hatırladığım önceki bir komut yok efendim.")
                self.status.emit("AKTIF")
                self.finished.emit(True)
                return True
        elif normalized_text not in ["bunu yap", "devam et"]:
            self.last_meaningful_command = text
        self.remember_dialog("user", text)
        self.brain.remember_from_text(text)

        v3_result = self.route_with_v3(text)

        if v3_result == "EXIT":
            self.record_command_result(text, "v3_exit", "Program kapatildi.", success=True)
            self.speak("GÃ¶rÃ¼ÅŸÃ¼rÃ¼z efendim.")
            self.finished.emit(False)
            return False

        if v3_result == "DONE":
            self.record_command_result(text, "v3_done", "Islem tamamlandi veya onay bekliyor.", success=True)
            self.status.emit("OYUN MODU" if self.mode == "OYUN" else "AKTIF")
            self.finished.emit(True)
            return True

        if v3_result:
            self.record_command_result(text, "v3", v3_result, success=True)
            self.last_action_summary = v3_result
            if speak_result:
                self.speak(v3_result)
            else:
                self.log.emit(f"> JARVIS: {v3_result}")
            self.remember_dialog("assistant", v3_result)
            self.learn_from_exchange_async(text, v3_result)
            self.status.emit("AKTIF")
            self.finished.emit(True)
            return True

        result = self.computer_command(text)

        if result == "EXIT":
            self.record_command_result(text, "local_exit", "Program kapatildi.", success=True)
            self.speak("Görüşürüz efendim.")
            self.finished.emit(False)
            return False

        if result == "DONE":
            self.record_command_result(text, "local_done", "Islem tamamlandi veya onay bekliyor.", success=True)
            self.status.emit("OYUN MODU" if self.mode == "OYUN" else "AKTIF")
            self.finished.emit(True)
            return True

        if result:
            self.record_command_result(text, "local", result, success=True)
            self.last_action_summary = result
            if speak_result:
                self.speak(result)
            else:
                self.log.emit(f"> JARVIS: {result}")
            self.remember_dialog("assistant", result)
            self.learn_from_exchange_async(text, result)
            self.status.emit("AKTIF")
            self.finished.emit(True)
            return True

        try:
            answer = self.ask_gpt_manager(text)
        except Exception as exc:
            answer = f"OpenAI yanıtı alınamadı: {exc}"

        if speak_result:
            self.speak(answer)
        else:
            self.log.emit(f"> JARVIS: {answer}")
        self.last_action_summary = "Sohbet yaniti verdim; fiziksel bir islem yapmadim."
        self.remember_dialog("assistant", answer)
        self.record_command_result(text, "chat", answer, success=not answer.startswith("OpenAI"))
        self.learn_from_exchange_async(text, answer)
        self.status.emit("AKTIF")
        self.finished.emit(True)
        return True

    def listen_once(self):
        self.status.emit("DINLIYOR")
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=MIC_AMBIENT_DURATION)
            audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=12)
        return self.transcribe_audio(audio)

    def transcribe_audio(self, audio):
        if self.client:
            try:
                audio_file = io.BytesIO(audio.get_wav_data())
                audio_file.name = "jarvis_command.wav"
                transcript = self.client.audio.transcriptions.create(
                    model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
                    file=audio_file,
                    language="tr",
                    prompt=(
                        "Turkce konusan bir kullanici Windows icin JARVIS'e komut veriyor. "
                        "Uygulama adlari, site adlari, muzik adlari ve kisi adlarini mumkun oldugunca koru."
                    ),
                )
                text = getattr(transcript, "text", "").strip()
                if text:
                    return text
            except Exception as exc:
                self.log.emit(f"> SES: OpenAI transkripsiyon kullanilamadi, Google deneniyor: {exc}")

        return self.recognizer.recognize_google(audio, language="tr-TR")


class CommandWorker(QObject):
    done = pyqtSignal()

    def __init__(self, core, text=None, listen=False):
        super().__init__()
        self.core = core
        self.text = text
        self.listen = listen

    def run(self):
        try:
            text = self.text
            if self.listen:
                text = self.core.listen_once()
            if text:
                self.core.handle_command(text)
        except sr.WaitTimeoutError:
            self.core.record_command_result(self.text or "sesli komut", "listen_timeout", "Ses algilanmadi.", success=False)
            self.core.status.emit("AKTIF")
            self.core.speak("Komut duyamadım efendim.")
        except sr.UnknownValueError:
            self.core.record_command_result(self.text or "sesli komut", "speech_unknown", "Ses metne cevrilemedi.", success=False)
            self.core.status.emit("AKTIF")
            self.core.speak("Anlayamadım efendim.")
        except Exception as exc:
            self.core.record_command_result(self.text or "komut", "worker_error", str(exc), success=False)
            self.core.log.emit(f"> HATA: {exc}")
            self.core.status.emit("HATA")
        finally:
            self.done.emit()


class WakeWorker(QObject):
    wake_state = pyqtSignal(str)
    stopped = pyqtSignal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        if Model is None or pyaudio is None or np is None:
            self.core.log.emit("> WAKE: Gerekli ses paketleri eksik. MIKROFON butonu calismaya devam eder.")
            self.stopped.emit()
            return

        stream = None
        audio = None
        try:
            self.wake_state.emit("WAKE BEKLEMEDE")
            try:
                model_path = openwakeword.MODELS["hey_jarvis"]["model_path"].replace(".tflite", ".onnx")
                model = Model(wakeword_models=[model_path], inference_framework="onnx")
            except Exception:
                self.core.log.emit("> WAKE: Model dosyasi eksik. Simdilik MIKROFON butonunu kullan.")
                self.core.log.emit("> IPUCU: Terminalde su dosyayi calistir: .\\download_wake_models.bat")
                self.stopped.emit()
                return

            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=CHUNK,
            )
            last_wake = 0

            while self.running:
                audio_data = stream.read(CHUNK, exception_on_overflow=False)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                prediction = model.predict(audio_array)
                score = max(prediction.values())

                if score > WAKE_THRESHOLD and time.time() - last_wake > 2:
                    last_wake = time.time()
                    if not self.core.quiet_mode:
                        self.core.speak("Dinliyorum efendim.")
                    try:
                        command = self.core.listen_once()
                        if not self.core.handle_command(command):
                            self.running = False
                    except sr.WaitTimeoutError:
                        self.core.speak("Komut duyamadım efendim.")
                    except sr.UnknownValueError:
                        self.core.speak("Anlayamadım efendim.")
                    except Exception as exc:
                        self.core.log.emit(f"> WAKE HATASI: {exc}")

                    last_wake = time.time()
                    QThread.msleep(20)
        except Exception as exc:
            self.core.log.emit(f"> WAKE: Dinleme baslatilamadi: {exc}")
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            if audio is not None:
                audio.terminate()
            self.wake_state.emit("AKTIF")
            self.stopped.emit()


class JarvisUI(QWidget):
    # ESKİ → güncellendi
    def __init__(self, start_mini=False, start_silent=False):
        super().__init__()
        self.core = JarvisCore()
        if start_silent:
            self.core.quiet_mode = True
        self.command_thread = None
        self.command_worker = None
        self.wake_thread = None
        self.wake_worker = None
        self.drag_pos = QPoint()
        self.pulse = 0
        self.compact_geometry = None
        self.expanded = False
        self.mini_mode = False
        self.cockpit_mode = False
        self.cockpit_tab = "HOME"
        self.plan_scope = "BUGUN"
        self.normal_geometry = None
        self.pre_cockpit_geometry = None
        self.restore_cockpit_after_mini = False
        self.speaking_active = False
        self.listening_active = False
        self.performance_mode = True
        self.voice_energy = 0.0
        self.title_jitter = 0.0
        self.matrix_columns = []
        self.scanline = 0
        self.riot_safe_mode = False
        self.riot_wake_was_running = False
        self.riot_quiet_was_enabled = False
        self.queued_text = None
        self.cpu_percent = 0.0
        self.ram_percent = 0.0
        self.system_stats_text = "CPU: %0  RAM: %0"
        self._last_cpu_times = None

        self.setWindowTitle("J.A.R.V.I.S")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        x, y, width, height = self.default_panel_geometry()
        self.setFixedSize(width, height)
        self.move(x, y)
        self.normal_geometry = self.geometry()

        self.chat = QTextEdit(self)
        self.chat.setReadOnly(True)
        self.chat.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 3, 2, 145);
                color: #b8ffd0;
                border: none;
                border-radius: 4px;
                font-family: Consolas;
                font-size: 10px;
                padding: 6px;
                selection-background-color: #00ff66;
                selection-color: #021707;
            }
        """)
        self.chat.append("> JARVIS ONLINE")

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Komut yaz...")
        self.input.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 18, 14, 210);
                color: #b8ffd0;
                border: 1px solid #00ff66;
                border-radius: 5px;
                padding-left: 10px;
                font-family: Consolas;
                font-size: 10px;
            }
        """)
        self.input.returnPressed.connect(self.send_text)

        self.send_btn = QPushButton("GONDER  ▶", self)
        self.send_btn.clicked.connect(self.send_text)

        self.mic_btn = QPushButton("", self)
        self.mic_btn.clicked.connect(self.listen_once)
        self.mic_btn.setToolTip("Ortadaki cekirdege tikla: JARVIS tek seferlik komut dinler.")

        self.wake_btn = QPushButton("WAKE", self)
        self.wake_btn.clicked.connect(self.toggle_wake)
        self.wake_btn.hide()

        self.mute_btn = QPushButton("SUSTUR", self)
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.mute_btn.setToolTip("JARVIS konusuyorsa hemen susturur. Sessiz mod aciksa tekrar sesi acar.")

        self.file_btn = QPushButton("DOSYA", self)
        self.file_btn.clicked.connect(self.select_file)
        self.file_btn.setToolTip("PDF, fotograf, ekran goruntusu veya metin dosyasi ekle.")

        self.min_btn = QPushButton("−", self)
        self.min_btn.clicked.connect(self.enter_mini_mode)

        self.max_btn = QPushButton("□", self)
        self.max_btn.clicked.connect(self.toggle_panel_size)

        self.close_btn = QPushButton("×", self)
        self.close_btn.clicked.connect(self.close)

        for button in [self.send_btn, self.mic_btn, self.mute_btn, self.file_btn, self.min_btn, self.max_btn, self.close_btn]:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet("""
                QPushButton {
                    background: rgba(0, 48, 35, 210);
                    color: #bdffd0;
                    border: 1px solid #00ff66;
                    border-radius: 5px;
                    font-family: Consolas;
                    font-weight: bold;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background: #00ff66;
                    color: #001904;
                }
            """)

        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
        """)
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background: rgba(45, 8, 6, 215);
                color: #ffdfc2;
                border: 1px solid #ff7a3d;
                border-radius: 5px;
                font-family: Consolas;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover {
                background: #ff7a3d;
                color: #130400;
            }
        """)

        self.core.log.connect(self.add_log)
        self.core.status.connect(self.set_status)
        self.core.finished.connect(self.on_core_finished)
        self.core.speaking.connect(self.set_speaking)
        self.core.ui_command.connect(self.handle_ui_command)
        self.current_status = "AKTIF"

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(90)

        self.riot_timer = QTimer(self)
        self.riot_timer.timeout.connect(self.check_riot_safe_mode)
        self.riot_timer.start(3000)

        # ESKİ → güncellendi
        self.system_stats_timer = QTimer(self)
        self.system_stats_timer.timeout.connect(self.update_system_stats)
        self.update_system_stats()
        self.system_stats_timer.start(2000)

        self.init_matrix()
        self.apply_layout()

        if start_mini:
            QTimer.singleShot(0, self.enter_mini_mode)
        elif "--cockpit" in sys.argv:
            QTimer.singleShot(0, self.enter_cockpit_mode)

        QTimer.singleShot(500, self.start_wake_auto)

    def update_system_stats(self):
        try:
            if psutil is not None:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
            else:
                cpu = self.windows_cpu_percent()
                ram = self.windows_ram_percent()
            if cpu is None or ram is None:
                self.system_stats_text = "CPU: --  RAM: --"
                self.update()
                return
            self.cpu_percent = cpu
            self.ram_percent = ram
            self.system_stats_text = f"CPU: %{cpu:.0f}  RAM: %{ram:.0f}"
            self.update()
        except Exception as exc:
            self.system_stats_text = "CPU: --  RAM: --"
            self.core.log_event("HATA", f"Sistem istatistikleri okunamadi: {exc}")
            self.update()

    def windows_cpu_percent(self):
        class FileTime(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

        def to_int(value):
            return (value.dwHighDateTime << 32) + value.dwLowDateTime

        idle = FileTime()
        kernel = FileTime()
        user = FileTime()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None

        idle_time = to_int(idle)
        total_time = to_int(kernel) + to_int(user)
        previous = self._last_cpu_times
        self._last_cpu_times = (idle_time, total_time)
        if not previous:
            return self.cpu_percent

        idle_delta = idle_time - previous[0]
        total_delta = total_time - previous[1]
        if total_delta <= 0:
            return self.cpu_percent
        return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))

    def windows_ram_percent(self):
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return float(status.dwMemoryLoad)

    def apply_layout(self):
        if self.mini_mode:
            for widget in [self.chat, self.input, self.send_btn, self.mic_btn, self.wake_btn, self.mute_btn, self.file_btn, self.min_btn, self.max_btn, self.close_btn]:
                widget.hide()
            return

        for widget in [self.chat, self.input, self.send_btn, self.mic_btn, self.mute_btn, self.file_btn, self.min_btn, self.max_btn, self.close_btn]:
            widget.show()
        self.wake_btn.hide()

        w = self.width()
        h = self.height()

        if self.cockpit_mode:
            self.min_btn.setGeometry(w - 108, 14, 26, 24)
            self.max_btn.setGeometry(w - 76, 14, 26, 24)
            self.close_btn.setGeometry(w - 44, 14, 28, 24)
            self.chat.setGeometry(int(w * 0.728), int(h * 0.722), int(w * 0.233), int(h * 0.142))
            self.input.setGeometry(int(w * 0.36), int(h * 0.828), int(w * 0.225), 40)
            self.send_btn.setGeometry(int(w * 0.596), int(h * 0.828), int(w * 0.095), 40)
            self.mic_btn.setGeometry(int(w * 0.44), int(h * 0.34), int(w * 0.12), int(w * 0.12))
            self.mute_btn.setGeometry(18, h - 42, 80, 28)
            self.file_btn.setGeometry(106, h - 42, 80, 28)
            return

        margin = int(w * 0.075)
        self.min_btn.setGeometry(w - 94, 10, 24, 24)
        self.max_btn.setGeometry(w - 66, 10, 24, 24)
        self.close_btn.setGeometry(w - 38, 10, 26, 24)
        self.chat.setGeometry(margin, int(h * 0.388), w - margin * 2, int(h * 0.238))
        self.input.setGeometry(margin + 6, int(h * 0.662), int(w * 0.52), 36)
        self.send_btn.setGeometry(int(w * 0.655), int(h * 0.662), int(w * 0.26), 36)
        self.mic_btn.setGeometry(int(w * 0.39), int(h * 0.755), int(w * 0.22), int(w * 0.22))
        # ESKİ → güncellendi
        self.mute_btn.setGeometry(14, h - 40, 80, 28)
        self.file_btn.setGeometry(102, h - 40, 80, 28)

    def init_matrix(self):
        step = 22 if self.cockpit_mode and self.performance_mode else (13 if self.cockpit_mode else 9)
        columns = max(28, self.width() // step)
        self.matrix_columns = []
        alphabet = "01010110JARVISAI//SYSRUNTRONCORE"
        for index in range(columns):
            self.matrix_columns.append({
                "x": 6 + index * step + random.randint(-1, 1),
                "y": random.randint(-self.height(), self.height()),
                "speed": random.uniform(0.65, 2.1 if self.cockpit_mode and self.performance_mode else (3.0 if self.cockpit_mode else 3.7)),
                "length": random.randint(12 if self.cockpit_mode and self.performance_mode else (18 if self.cockpit_mode else 16), 28 if self.cockpit_mode and self.performance_mode else (42 if self.cockpit_mode else 42)),
                "chars": [random.choice(alphabet) for _ in range(24)],
            })

    def tick(self):
        self.pulse = (self.pulse + 1) % 180
        self.update_mute_button()
        target = 0.0
        if self.speaking_active:
            target = max(0.28, self.core.voice_volume)
        elif self.listening_active:
            target = 0.42 + math.sin(self.pulse * 0.2) * 0.12
        self.voice_energy += (target - self.voice_energy) * 0.18
        self.title_jitter = math.sin(self.pulse * 0.22) * (2.0 + self.voice_energy * 5.0)
        self.scanline = (self.scanline + 3) % max(1, self.height())
        for column in self.matrix_columns:
            column["y"] += column["speed"] * (1.0 + self.voice_energy * 0.6)
            if column["y"] > self.height() + 120:
                column["y"] = random.randint(-220, -20)
        self.update()

    def add_log(self, text):
        self.chat.append(text)
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
        if any(marker in str(text).upper() for marker in ["HATA", "ERROR", "FAILED"]):
            self.core.log_event("HATA", str(text))

    def set_status(self, text):
        self.current_status = text
        self.listening_active = text in ["DINLIYOR", "WAKE ALGILANDI"]
        self.update()

    def set_speaking(self, active):
        self.speaking_active = active
        self.update_mute_button()
        self.update()

    def update_mute_button(self):
        if getattr(self.core, "quiet_mode", False):
            desired = "SES AC"
        else:
            desired = "SUSTUR"
        if self.mute_btn.text() != desired:
            self.mute_btn.setText(desired)

    def toggle_mute(self):
        if self.core.quiet_mode:
            self.core.quiet_mode = False
            self.add_log("> SISTEM: Sesli cevaplar yeniden acildi.")
        else:
            self.core.stop_speaking()
            self.core.quiet_mode = True
            self.add_log("> SISTEM: JARVIS susturuldu. Yazili cevap vermeye devam edecek.")
        self.update_mute_button()
        self.update()

    def select_file(self):
        filters = (
            "JARVIS destekli dosyalar (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.txt *.md *.csv *.json *.docx *.py *.log);;"
            "Tum dosyalar (*.*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(self, "JARVIS'e dosya ekle", str(Path.home()), filters)
        if not file_path:
            return
        result = self.core.set_attached_file(file_path)
        self.add_log(f"> DOSYA: {result}")
        self.core.speak("Dosya eklendi. Taramamı istersen bu dosyayı tara ve özetini anlat de.")
        self.update()

    def handle_ui_command(self, command):
        if command == "show_panel":
            if self.mini_mode:
                self.leave_mini_mode()
            self.showNormal()
            self.raise_()
            self.activateWindow()
        elif command == "wake_on":
            self.start_wake_auto()
        elif command == "wake_off":
            self.stop_wake_auto()
        elif command == "cockpit_on":
            self.enter_cockpit_mode()
            self.raise_()
            self.activateWindow()
        elif command == "cockpit_off":
            self.leave_cockpit_mode()
        elif command == "mini_on":
            self.enter_mini_mode()
        elif command == "select_file":
            self.select_file()
        elif command.startswith("tab:"):
            self.enter_cockpit_mode()
            self.cockpit_tab = command.split(":", 1)[1]
            self.update()
        elif command.startswith("plan:"):
            self.enter_cockpit_mode()
            self.cockpit_tab = "PLANNER"
            self.plan_scope = "YARIN" if command.endswith("yarin") else "BUGUN"
            self.update()
        elif command == "performance_on":
            self.performance_mode = True
            self.timer.setInterval(90)
            self.init_matrix()
            self.update()
        elif command == "performance_off":
            self.performance_mode = False
            self.timer.setInterval(45)
            self.init_matrix()
            self.update()

    def riot_process_active(self):
        target_names = [
            "riotclientux.exe",
            "riotclientuxrender.exe",
            "leagueclient.exe",
            "leagueclientux.exe",
            "league of legends.exe",
            "valorant.exe",
            "valorant-win64-shipping.exe",
        ]
        try:
            completed = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return False

        output = completed.stdout.lower()
        return any(name in output for name in target_names)

    def check_riot_safe_mode(self):
        active = self.riot_process_active()
        if active and not self.riot_safe_mode:
            self.enter_riot_safe_mode()
        elif not active and self.riot_safe_mode:
            self.leave_riot_safe_mode()

    def enter_riot_safe_mode(self):
        self.riot_safe_mode = True
        self.riot_wake_was_running = self.wake_thread is not None
        self.riot_quiet_was_enabled = self.core.quiet_mode
        self.core.quiet_mode = True
        self.add_log("> SISTEM: Riot guvenli modu aktif. Wake ve otomasyon sessize alindi.")
        self.stop_wake_auto()
        self.enter_mini_mode()

    def leave_riot_safe_mode(self):
        self.riot_safe_mode = False
        self.core.quiet_mode = self.riot_quiet_was_enabled
        self.add_log("> SISTEM: Riot guvenli modu kapandi. JARVIS normale donuyor.")
        self.leave_mini_mode()
        self.raise_()
        self.activateWindow()
        if self.riot_wake_was_running:
            QTimer.singleShot(800, self.start_wake_auto)

    def on_core_finished(self, should_continue):
        if not should_continue:
            self.close()

    def start_command_worker(self, text=None, listen=False):
        if self.command_thread is not None:
            if text:
                self.queued_text = text
                self.core.stop_speaking()
                self.add_log("> SISTEM: Konusma kesildi. Yeni komut siraya alindi.")
            else:
                self.add_log("> SISTEM: JARVIS su an bir komut isliyor.")
            return

        self.send_btn.setEnabled(False)
        self.mic_btn.setEnabled(False)
        self.command_thread = QThread()
        self.command_worker = CommandWorker(self.core, text=text, listen=listen)
        self.command_worker.moveToThread(self.command_thread)
        self.command_thread.started.connect(self.command_worker.run)
        self.command_worker.done.connect(self.command_thread.quit)
        self.command_worker.done.connect(self.command_worker.deleteLater)
        self.command_thread.finished.connect(self.command_thread.deleteLater)
        self.command_thread.finished.connect(self.enable_controls)
        self.command_thread.start()

    def enable_controls(self):
        self.send_btn.setEnabled(True)
        self.mic_btn.setEnabled(True)
        self.command_thread = None
        self.command_worker = None
        if self.queued_text:
            queued = self.queued_text
            self.queued_text = None
            self.add_log("> SISTEM: Siradaki komut isleniyor.")
            QTimer.singleShot(60, lambda: self.start_command_worker(text=queued))

    def send_text(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        if self.speaking_active:
            self.core.stop_speaking()
            self.add_log("> SISTEM: Konusma kesildi.")
        self.start_command_worker(text=text)

    def listen_once(self):
        self.add_log("> SISTEM: Mikrofon dinliyor. Konusabilirsin.")
        self.start_command_worker(listen=True)

    def toggle_wake(self):
        if self.wake_thread is not None:
            self.wake_btn.setText("WAKE")
            self.wake_btn.setEnabled(False)
            self.wake_worker.stop()
            return

        self.wake_btn.setText("DURDUR")
        self.wake_thread = QThread()
        self.wake_worker = WakeWorker(self.core)
        self.wake_worker.moveToThread(self.wake_thread)
        self.wake_thread.started.connect(self.wake_worker.run)
        self.wake_worker.wake_state.connect(self.set_status)
        self.wake_worker.stopped.connect(self.wake_thread.quit)
        self.wake_worker.stopped.connect(self.wake_worker.deleteLater)
        self.wake_thread.finished.connect(self.wake_thread.deleteLater)
        self.wake_thread.finished.connect(self.wake_finished)
        self.wake_thread.start()

    def start_wake_auto(self):
        if self.riot_safe_mode:
            return
        if self.wake_thread is None:
            self.toggle_wake()

    def stop_wake_auto(self):
        if self.wake_thread is not None and self.wake_worker is not None:
            self.wake_worker.stop()
            return True
        return False

    def wake_finished(self):
        self.wake_thread = None
        self.wake_worker = None
        self.wake_btn.setText("WAKE")
        self.wake_btn.setEnabled(True)

    def default_panel_geometry(self):
        screen = QApplication.primaryScreen().availableGeometry()
        width = max(420, min(460, int(screen.width() * 0.23)))
        height = int(width * 1.22)
        x = screen.right() - width - 18
        y = screen.bottom() - height - 42
        return x, y, width, height

    def enter_mini_mode(self):
        if not self.mini_mode:
            self.normal_geometry = self.geometry()
            self.restore_cockpit_after_mini = self.cockpit_mode
        self.mini_mode = True
        self.expanded = False
        self.cockpit_mode = False
        self.setFixedSize(184, 44)
        self.move(8, 8)
        self.apply_layout()
        self.update()

    def leave_mini_mode(self):
        self.mini_mode = False
        if self.restore_cockpit_after_mini:
            self.restore_cockpit_after_mini = False
            self.enter_cockpit_mode()
            return
        self.cockpit_mode = False
        if self.normal_geometry:
            self.setFixedSize(self.normal_geometry.width(), self.normal_geometry.height())
            self.move(self.normal_geometry.topLeft())
        else:
            x, y, width, height = self.default_panel_geometry()
            self.setFixedSize(width, height)
            self.move(x, y)
        self.apply_layout()
        self.update()

    def cockpit_geometry(self):
        screens = QApplication.screens()
        screen = screens[1] if len(screens) > 1 else QApplication.primaryScreen()
        available = screen.availableGeometry()
        width = int(available.width() * 0.92)
        height = int(width * 0.56)
        max_height = int(available.height() * 0.88)
        if height > max_height:
            height = max_height
            width = int(height / 0.56)
        width = max(860, min(width, available.width() - 40))
        height = max(500, min(height, available.height() - 50))
        x = available.x() + (available.width() - width) // 2
        y = available.y() + (available.height() - height) // 2
        return x, y, width, height

    def enter_cockpit_mode(self):
        was_mini = self.mini_mode
        if self.mini_mode:
            self.mini_mode = False
        if not self.cockpit_mode:
            current = self.geometry()
            if was_mini or current.width() < 300 or current.height() < 260:
                self.pre_cockpit_geometry = None
            else:
                self.pre_cockpit_geometry = current
        self.cockpit_mode = True
        self.expanded = True
        x, y, width, height = self.cockpit_geometry()
        self.setFixedSize(width, height)
        self.move(x, y)
        self.max_btn.setText("□")
        self.init_matrix()
        self.apply_layout()
        self.update()

    def leave_cockpit_mode(self):
        self.cockpit_mode = False
        self.expanded = False
        if self.pre_cockpit_geometry and self.pre_cockpit_geometry.width() >= 300 and self.pre_cockpit_geometry.height() >= 260:
            self.setFixedSize(self.pre_cockpit_geometry.width(), self.pre_cockpit_geometry.height())
            self.move(self.pre_cockpit_geometry.topLeft())
        else:
            x, y, width, height = self.default_panel_geometry()
            self.setFixedSize(width, height)
            self.move(x, y)
        self.max_btn.setText("□")
        self.init_matrix()
        self.apply_layout()
        self.update()

    def toggle_panel_size(self):
        if self.mini_mode:
            self.leave_mini_mode()
            return

        if self.cockpit_mode:
            self.leave_cockpit_mode()
            return

        self.enter_cockpit_mode()
        return

        screen = QApplication.primaryScreen().availableGeometry()

        if not self.expanded:
            self.compact_geometry = self.geometry()
            width = max(460, min(510, int(screen.width() * 0.26)))
            height = int(width * 1.22)
            self.setFixedSize(width, height)
            self.move(screen.right() - width - 24, screen.bottom() - height - 42)
            self.max_btn.setText("▢")
            self.expanded = True
        else:
            if self.compact_geometry:
                self.setFixedSize(self.compact_geometry.width(), self.compact_geometry.height())
                self.move(self.compact_geometry.topLeft())
            self.max_btn.setText("□")
            self.expanded = False

        self.apply_layout()
        self.update()

    def cockpit_nav_rects(self):
        w = self.width()
        h = self.height()
        y = int(h * 0.03)
        rects = []
        for i, item in enumerate(["HOME", "DASHBOARD", "PLANNER", "SETTINGS"]):
            rects.append((item, QRectF(int(w * (0.71 + i * 0.058)), y, int(w * 0.052), 26)))
        return rects

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.cockpit_mode and not self.mini_mode:
                for item, rect in self.cockpit_nav_rects():
                    if rect.contains(event.position()):
                        if self.cockpit_tab == item:
                            event.accept()
                            return
                        self.cockpit_tab = item
                        labels = {"HOME": "REHBER", "DASHBOARD": "SISTEM", "PLANNER": "PLAN", "SETTINGS": "AYARLAR"}
                        self.add_log(f"> PANEL: {labels.get(item, item)} acildi.")
                        self.update()
                        event.accept()
                        return
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if self.mini_mode and event.button() == Qt.MouseButton.LeftButton:
            self.leave_mini_mode()
            event.accept()

    def closeEvent(self, event):
        if self.wake_worker:
            self.wake_worker.stop()
        self.core.log_shutdown()
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        green = QColor(0, 255, 102)
        soft = QColor(0, 255, 102, 85)
        bg = QRectF(0, 0, w - 1, h - 1)

        if self.mini_mode:
            path = QPainterPath()
            path.addRoundedRect(bg, 10, 10)
            painter.fillPath(path, QColor(0, 9, 8, 245))
            painter.setPen(QPen(QColor(0, 255, 190, 170), 1))
            painter.drawPath(path)

            glow = 80 + int(90 * abs(math.sin(self.pulse * 0.12)))
            active = self.listening_active or self.speaking_active
            painter.setPen(QPen(QColor(0, 255, 190, glow if active else 95), 2))
            painter.drawEllipse(QPoint(20, h // 2), 8, 8)
            painter.setBrush(QColor(0, 255, 160, 230 if active else 140))
            painter.drawEllipse(QPoint(20, h // 2), 3, 3)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            painter.setPen(QColor(100, 255, 225, 235))
            painter.drawText(QRectF(36, 6, 86, 16), Qt.AlignmentFlag.AlignLeft, "JARVIS")
            painter.setFont(QFont("Consolas", 6, QFont.Weight.Bold))
            state = "SESSIZ" if self.core.quiet_mode else ("KONUSUYOR" if self.speaking_active else ("DINLIYOR" if self.listening_active else "HAZIR"))
            painter.setPen(QColor(180, 255, 230, 155))
            painter.drawText(QRectF(38, 24, 88, 12), Qt.AlignmentFlag.AlignLeft, state)

            painter.setPen(QPen(QColor(0, 255, 190, 120), 1))
            base_y = h // 2
            last_x = 124
            last_y = base_y
            for i in range(27):
                x = 124 + i * 2
                amp = 4 + self.voice_energy * 10
                y = base_y + math.sin(i * 0.8 + self.pulse * 0.22) * amp
                painter.drawLine(last_x, int(last_y), x, int(y))
                last_x, last_y = x, y
            return

        if self.cockpit_mode:
            self.draw_cockpit_dashboard(painter, w, h, green, soft)
            return

        path = QPainterPath()
        path.addRoundedRect(bg, 8, 8)
        painter.fillPath(path, QColor(0, 3, 2, 248))
        painter.setPen(QPen(QColor(0, 255, 102, 105), 1))
        painter.drawPath(path)

        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0, QColor(0, 28, 12, 70))
        gradient.setColorAt(0.5, QColor(0, 0, 0, 0))
        gradient.setColorAt(1, QColor(0, 55, 18, 55))
        painter.fillPath(path, gradient)

        self.draw_matrix_rain(painter, w, h, green)

        painter.setPen(QPen(QColor(0, 255, 102, 12), 1))
        for x in range(12, w, 18):
            painter.drawLine(x, 44, x, h - 44)
        for y in range(48, h, 20):
            painter.drawLine(8, y, w - 8, y)

        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        painter.setPen(green)
        painter.drawText(18, 25, f"◉  JARVIS {APP_VERSION}")

        self.draw_panel_frames(painter, w, h)
        self.draw_core(painter, w, h, green, soft)
        self.draw_title(painter, w, h, green)
        self.draw_status_plate(painter, w, h, green)
        self.draw_wave(painter, w, h, green)
        self.draw_footer(painter, w, h, green)

    def hud_box(self, painter, rect, title="", glow=85):
        x, y, rw, rh = rect.x(), rect.y(), rect.width(), rect.height()
        cut = min(18, max(8, int(rh * 0.12)))
        path = QPainterPath()
        path.moveTo(x + cut, y)
        path.lineTo(x + rw - cut, y)
        path.lineTo(x + rw, y + cut)
        path.lineTo(x + rw, y + rh)
        path.lineTo(x, y + rh)
        path.lineTo(x, y + cut)
        path.closeSubpath()
        painter.fillPath(path, QColor(0, 8, 9, 222 if self.cockpit_mode else 178))
        painter.setPen(QPen(QColor(0, 255, 190, glow), 3))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(0, 255, 190, 190), 1))
        painter.drawPath(path)
        if title:
            painter.setFont(QFont("Consolas", max(7, int(self.width() * 0.008)), QFont.Weight.Bold))
            painter.setPen(QColor(0, 255, 190, 220))
            painter.drawText(QRectF(x + 14, y + 10, rw - 26, 16), Qt.AlignmentFlag.AlignLeft, title)

    def draw_cockpit_dashboard(self, painter, w, h, green, soft):
        bg = QRectF(0, 0, w - 1, h - 1)
        path = QPainterPath()
        path.addRoundedRect(bg, 3, 3)
        painter.fillPath(path, QColor(0, 5, 7, 250))
        painter.setPen(QPen(QColor(0, 255, 190, 130), 1))
        painter.drawPath(path)

        gradient = QLinearGradient(0, 0, w, h)
        gradient.setColorAt(0, QColor(0, 42, 36, 85))
        gradient.setColorAt(0.45, QColor(0, 9, 12, 10))
        gradient.setColorAt(1, QColor(0, 65, 42, 70))
        painter.fillPath(path, gradient)

        self.draw_matrix_rain(painter, w, h, green)
        self.draw_cockpit_grid(painter, w, h)

        painter.setFont(QFont("Consolas", max(10, int(w * 0.012)), QFont.Weight.Bold))
        painter.setPen(QColor(34, 255, 226, 235))
        painter.drawText(int(w * 0.17), int(h * 0.072), "J.A.R.V.I.S.")

        self.draw_cockpit_nav(painter, w, h)

        painter.setFont(QFont("Arial", max(30, int(w * 0.04)), QFont.Weight.Bold))
        painter.setPen(QColor(235, 255, 250, 245))
        title = {
            "HOME": "JARVIS REHBERI",
            "DASHBOARD": "SISTEM PANELI",
            "PLANNER": "GUNLUK PLAN",
            "SETTINGS": "JARVIS AYARLARI",
        }.get(self.cockpit_tab, "JARVIS COCKPIT")
        painter.drawText(QRectF(0, int(h * 0.16), w, 70), Qt.AlignmentFlag.AlignCenter, title)

        self.draw_cockpit_orb(painter, w, h)
        self.draw_cockpit_panels(painter, w, h)
        self.draw_cockpit_tab_detail(painter, w, h)
        self.draw_cockpit_center_card(painter, w, h)
        self.draw_cockpit_wave(painter, w, h)

    def draw_cockpit_nav(self, painter, w, h):
        font = QFont("Consolas", max(6, int(w * 0.0065)), QFont.Weight.Bold)
        painter.setFont(font)
        labels = {
            "HOME": "REHBER",
            "DASHBOARD": "SISTEM",
            "PLANNER": "PLAN",
            "SETTINGS": "AYARLAR",
        }
        for item, rect in self.cockpit_nav_rects():
            active = item == self.cockpit_tab
            if active:
                painter.fillRect(rect, QColor(0, 70, 64, 70))
                painter.setPen(QPen(QColor(0, 255, 190, 150), 1))
                painter.drawRoundedRect(rect, 5, 5)
                painter.setPen(QPen(QColor(0, 255, 190, 210), 2))
                painter.drawLine(int(rect.x() + 10), int(rect.bottom() - 4), int(rect.right() - 10), int(rect.bottom() - 4))
            painter.setPen(QColor(220, 255, 248, 245 if active else 165))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, labels.get(item, item))

    def draw_cockpit_grid(self, painter, w, h):
        painter.setPen(QPen(QColor(0, 255, 190, 16), 1))
        for x in range(int(w * 0.08), int(w * 0.92), max(36, int(w * 0.055))):
            painter.drawLine(x, int(h * 0.12), x, int(h * 0.88))
        for y in range(int(h * 0.13), int(h * 0.88), max(32, int(h * 0.075))):
            painter.drawLine(int(w * 0.08), y, int(w * 0.92), y)

        painter.setPen(QPen(QColor(0, 255, 190, 11), 1))
        for x in range(0, w, 28):
            for y in range(0, h, 24):
                if (x + y) % 56 == 0:
                    painter.drawPoint(x, y)

    def draw_cockpit_orb(self, painter, w, h):
        cx = w // 2
        cy = int(h * 0.43)
        radius = int(min(w, h) * 0.086)
        pulse = 1 + self.voice_energy * 0.18 + math.sin(self.pulse * 0.08) * 0.04
        active_color = QColor(0, 255, 190)
        if self.listening_active:
            active_color = QColor(70, 255, 130)
        elif self.speaking_active:
            active_color = QColor(60, 210, 255)
        painter.setPen(QPen(QColor(active_color.red(), active_color.green(), active_color.blue(), 26), 1))
        for r in [radius + 20, radius + 48, radius + 82, radius + 118]:
            painter.drawEllipse(QPoint(cx, cy), r, r)

        painter.setPen(QPen(QColor(active_color.red(), active_color.green(), active_color.blue(), 70), 10))
        painter.drawEllipse(QPoint(cx, cy), int(radius * (1.02 + self.voice_energy * 0.08)), int(radius * (1.02 + self.voice_energy * 0.08)))
        painter.setPen(QPen(QColor(0, 255, 190, 55), 1))
        painter.drawLine(cx - radius - 58, cy, cx - radius - 14, cy)
        painter.drawLine(cx + radius + 14, cy, cx + radius + 58, cy)

        for i in range(60):
            angle = (i * 6 + self.pulse * 1.8) * math.pi / 180
            inner = radius * 0.42
            outer = radius * pulse
            x1 = cx + math.cos(angle) * inner
            y1 = cy + math.sin(angle) * inner
            x2 = cx + math.cos(angle) * outer
            y2 = cy + math.sin(angle) * outer
            alpha = 22 + int(65 * abs(math.sin(i + self.pulse * 0.03)))
            painter.setPen(QPen(QColor(active_color.red(), active_color.green(), active_color.blue(), alpha), 2))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        orb = QPainterPath()
        orb.addEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        orb_gradient = QLinearGradient(cx - radius, cy - radius, cx + radius, cy + radius)
        orb_gradient.setColorAt(0, QColor(active_color.red(), active_color.green(), active_color.blue(), 235))
        orb_gradient.setColorAt(0.45, QColor(0, 75, 64, 230))
        orb_gradient.setColorAt(1, QColor(0, 255, 230, 185))
        painter.fillPath(orb, orb_gradient)
        painter.setPen(QPen(QColor(110, 255, 230, 190), 2))
        painter.drawPath(orb)

        painter.setPen(QPen(QColor(220, 255, 240, 160), 2))
        arc_rect = QRectF(cx - radius * 0.72, cy - radius * 0.72, radius * 1.44, radius * 1.44)
        painter.drawArc(arc_rect, int((self.pulse * 3) % 360) * 16, 110 * 16)

        painter.setPen(QPen(QColor(0, 5, 5, 170), 3))
        painter.setFont(QFont("Consolas", max(10, int(w * 0.012)), QFont.Weight.Bold))
        label = "DINLIYOR" if self.listening_active else ("KONUSUYOR" if self.speaking_active else "DINLE")
        painter.drawText(QRectF(cx - radius, cy - 12, radius * 2, 24), Qt.AlignmentFlag.AlignCenter, label)
        painter.setPen(QColor(220, 255, 240, 230))
        painter.drawText(QRectF(cx - radius, cy - 12, radius * 2, 24), Qt.AlignmentFlag.AlignCenter, label)

        painter.setFont(QFont("Consolas", max(6, int(w * 0.006)), QFont.Weight.Bold))
        hint = "TIKLA VE KONUS" if not self.listening_active else "SES ALINIYOR..."
        painter.setPen(QColor(180, 255, 225, 185))
        painter.drawText(QRectF(cx - radius * 1.6, cy + radius + 12, radius * 3.2, 22), Qt.AlignmentFlag.AlignCenter, hint)

    def draw_cockpit_panels(self, painter, w, h):
        left = int(w * 0.035)
        right = int(w * 0.835)
        panel_w = int(w * 0.145)
        self.hud_box(painter, QRectF(left, int(h * 0.16), panel_w, int(h * 0.13)), "KONUM")
        left_mid_title = "DURUM" if self.cockpit_tab != "PLANNER" else "BUGUN"
        left_low_title = "AKTIVITE" if self.cockpit_tab != "SETTINGS" else "SES KONTROL"
        self.hud_box(painter, QRectF(left, int(h * 0.36), int(w * 0.18), int(h * 0.15)), left_mid_title)
        self.hud_box(painter, QRectF(left, int(h * 0.58), int(w * 0.16), int(h * 0.22)), left_low_title)
        self.hud_box(painter, QRectF(right, int(h * 0.13), int(w * 0.13), int(h * 0.16)), "CANLI DURUM")
        right_mid_title = "SAAT / BILGI" if self.cockpit_tab != "PLANNER" else "HATIRLATICI"
        self.hud_box(painter, QRectF(right, int(h * 0.36), int(w * 0.13), int(h * 0.27)), right_mid_title)
        self.hud_box(painter, QRectF(int(w * 0.708), int(h * 0.69), int(w * 0.265), int(h * 0.205)), "KOMUT GECMISI // J.A.R.V.I.S.")

        painter.setFont(QFont("Consolas", max(7, int(w * 0.007)), QFont.Weight.Bold))
        painter.setPen(QColor(170, 255, 225, 210))
        painter.drawText(left + 24, int(h * 0.205), "Istanbul / TR")
        painter.drawText(left + 24, int(h * 0.245), "SES BAGLANTISI HAZIR")

        top_status = [
            ("SISTEM CEVRIMICI", True),
            ("JARVIS AKTIF", True),
            ("V3 BEYIN", self.core.v3_enabled),
            ("MIKROFON IZNI", True),
            ("WAKE DINLIYOR", self.wake_thread is not None),
            ("API BAGLANTISI", self.core.client is not None),
        ]
        painter.setFont(QFont("Consolas", max(6, int(w * 0.006)), QFont.Weight.Bold))
        for i, (label, active) in enumerate(top_status):
            y = int(h * 0.175) + i * 18
            painter.setPen(QColor(140, 255, 225, 145))
            painter.drawText(right + 16, y, label)
            painter.setPen(QPen(QColor(0, 255, 120, 235) if active else QColor(255, 60, 60, 210), 5))
            painter.drawPoint(right + int(w * 0.105), y - 4)

        mic_state = "DINLIYOR" if self.listening_active else "HAZIR"
        memory_count = len(self.core.brain.memory.get("user_facts", [])) + len(self.core.brain.memory.get("project_notes", []))
        v3_state = "ACIK" if self.core.v3_enabled else "KAPALI"
        status_items = [("V3", v3_state), ("MIK", mic_state), ("HAFIZA", str(memory_count)), ("MOD", self.current_status)]
        if self.cockpit_tab == "PLANNER":
            plan_count = len(self.core.get_plan_items("yarin" if self.plan_scope == "YARIN" else "bugun"))
            status_items = [("GOREV", str(plan_count)), ("ODAK", "ACIK"), ("PLAN", self.plan_scope), ("MOD", "PLAN")]
        elif self.cockpit_tab == "SETTINGS":
            status_items = [("SES", f"{int(self.core.voice_volume * 100)}%"), ("V3", v3_state), ("RIOT", "GUVENLI"), ("HAFIZA", str(memory_count))]
        for i, (a, b) in enumerate(status_items):
            x = left + 20 + (i % 2) * int(w * 0.082)
            y = int(h * 0.405) + (i // 2) * int(h * 0.055)
            painter.fillRect(QRectF(x, y, int(w * 0.065), int(h * 0.035)), QColor(0, 40, 34, 155))
            painter.setPen(QColor(0, 255, 190, 210))
            painter.drawText(x + 8, y + 14, a)
            painter.setPen(QColor(185, 255, 225, 190))
            painter.drawText(x + 8, y + 28, b)

        logs = ["CEVAPLIYOR" if self.speaking_active else "BEKLEMEDE", "DINLEME", "KOMUT ALINDI", "ISLENIYOR", "WAKE ALGILANDI"]
        if self.cockpit_tab == "PLANNER":
            logs = ["BUGUNUN PLANI", "SIRADAKI GOREV", "HATIRLATICILAR", "ODAK BLOKU", "AKSAM OZETI"]
        elif self.cockpit_tab == "SETTINGS":
            logs = ["SES DUSUK", "WAKE ACIK", "MINI MOD HAZIR", "COCKPIT MODU", "RIOT GUVENLI"]
        for i, item in enumerate(logs):
            painter.setPen(QColor(0, 255, 190, 180 if i == 0 else 105))
            painter.drawText(left + 24, int(h * 0.63) + i * 22, f"{time.strftime('%H:%M:%S')}  -  {item}")

        painter.setFont(QFont("Consolas", max(9, int(w * 0.012)), QFont.Weight.Bold))
        painter.setPen(QColor(20, 255, 210, 235))
        painter.drawText(QRectF(right, int(h * 0.42), int(w * 0.13), 40), Qt.AlignmentFlag.AlignCenter, time.strftime("%H:%M"))
        painter.setFont(QFont("Consolas", max(7, int(w * 0.007)), QFont.Weight.Bold))
        painter.drawText(QRectF(right, int(h * 0.49), int(w * 0.13), 24), Qt.AlignmentFlag.AlignCenter, time.strftime("%d.%m.%Y"))
        painter.drawText(QRectF(right, int(h * 0.55), int(w * 0.13), 24), Qt.AlignmentFlag.AlignCenter, "CALISMA  //  KOMUT")

    def draw_cockpit_tab_detail(self, painter, w, h):
        memory_count = len(self.core.brain.memory.get("user_facts", [])) + len(self.core.brain.memory.get("project_notes", []))
        if self.cockpit_tab == "HOME":
            rect = QRectF(int(w * 0.22), int(h * 0.34), int(w * 0.20), int(h * 0.25))
            self.hud_box(painter, rect, "HIZLI REHBER", glow=60)
            items = [
                "1. Ortadaki DINLE cekirdegine tikla.",
                "2. Konusurken DINLIYOR yazisini bekle.",
                "3. Komut kutusuna yazarak da kullan.",
                "4. 'mini moda gec' veya 'plan ac' de.",
            ]
            self.draw_small_list(painter, rect, items, start_y=44)

            rect2 = QRectF(int(w * 0.59), int(h * 0.34), int(w * 0.20), int(h * 0.25))
            self.hud_box(painter, rect2, "ORNEK KOMUTLAR", glow=60)
            items2 = [
                "v3 durum",
                "bunu hatirla: ...",
                "neleri hatirliyorsun",
                "hizli virus taramasi yap",
                "spotify'da sarki ac",
                "siteyi turkceye cevir",
            ]
            self.draw_small_list(painter, rect2, items2, start_y=44)
        elif self.cockpit_tab == "DASHBOARD":
            rect = QRectF(int(w * 0.28), int(h * 0.58), int(w * 0.44), int(h * 0.08))
            self.hud_box(painter, rect, "ANLIK OKUMA", glow=45)
            items = [
                f"V3: {'acik' if self.core.v3_enabled else 'kapali'}",
                f"Hafiza kaydi: {memory_count}",
                f"Durum: {self.current_status}",
                f"Mikrofon: {'dinliyor' if self.listening_active else 'beklemede'}",
                f"JARVIS sesi: %{int(self.core.voice_volume * 100)}",
            ]
            self.draw_small_list(painter, rect, items, start_y=34, columns=3)
        elif self.cockpit_tab == "PLANNER":
            rect = QRectF(int(w * 0.27), int(h * 0.34), int(w * 0.46), int(h * 0.25))
            title = f"{self.plan_scope} PLANLARI"
            self.hud_box(painter, rect, title, glow=60)
            saved_items = self.core.get_plan_items("yarin" if self.plan_scope == "YARIN" else "bugun")
            if saved_items:
                items = []
                for item in saved_items[:7]:
                    time_text = item.get("time") or "--:--"
                    done = "OK" if item.get("done") else "  "
                    items.append(f"{time_text}  [{done}] {item.get('title', '')}")
            elif self.plan_scope == "YARIN":
                items = [
                    "Yarin icin kayitli plan yok.",
                    "Komut: 'yarin saat 10 spor yap diye ekle'",
                    "Komut: 'yarin saat 14 banka isini ekle'",
                    "Komut: 'yarin planimi oku'",
                ]
            else:
                items = [
                    "Simdilik kayitli gorev yok.",
                    "Komut: 'bugun saat 16 fatura ode diye ekle'",
                    "Komut: 'aksam bana spor yapmayi hatirlat'",
                    "Komut: 'bugunku planimi oku'",
                ]
            self.draw_small_list(painter, rect, items, start_y=44)
            route = QRectF(int(w * 0.74), int(h * 0.37), int(w * 0.20), int(h * 0.16))
            self.hud_box(painter, route, "SESLE YONET", glow=45)
            self.draw_small_list(painter, route, [
                "yarinin planlarini ac",
                "bugunun planlarini ac",
                "bugunku planimi oku",
                "saat ekleyerek gorev olustur",
            ], start_y=38)
        elif self.cockpit_tab == "SETTINGS":
            rect = QRectF(int(w * 0.27), int(h * 0.34), int(w * 0.46), int(h * 0.25))
            self.hud_box(painter, rect, "KONTROL KOMUTLARI", glow=60)
            items = [
                "v3 durum / v3 kapat / v3 ac",
                "bunu hatirla: ...",
                "neleri hatirliyorsun",
                "hafizayi temizle",
                "wake kapan / wake ac",
                "kendi sesini yuzde 20 yap",
                "sessiz bekle / tekrar konus",
            ]
            self.draw_small_list(painter, rect, items, start_y=44)

    def draw_small_list(self, painter, rect, items, start_y=36, columns=1):
        painter.setFont(QFont("Consolas", max(7, int(self.width() * 0.007)), QFont.Weight.Bold))
        for i, item in enumerate(items):
            col = i % columns
            row = i // columns
            x = rect.x() + 18 + col * (rect.width() / columns)
            y = rect.y() + start_y + row * 22
            painter.setPen(QColor(185, 255, 228, 205))
            painter.drawText(QRectF(x, y, rect.width() / columns - 24, 18), Qt.AlignmentFlag.AlignLeft, item)

    def draw_cockpit_center_card(self, painter, w, h):
        rect = QRectF(int(w * 0.39), int(h * 0.665), int(w * 0.25), int(h * 0.095))
        self.hud_box(painter, rect, "")
        lines = {
            "HOME": ("Nereden baslayabilirsin?", "Ortadaki cekirdege tikla veya 'Hey Jarvis' de."),
            "DASHBOARD": ("Sistem hazir.", f"V3 {'acik' if self.core.v3_enabled else 'kapali'}, ses ve komut baglantisi aktif."),
            "PLANNER": (f"{self.plan_scope.title()} plan anahtari", "Planlari sesle ac, oku ve yonet."),
            "SETTINGS": ("Ayar merkezi.", "V3, hafiza, ses ve wake kontrolleri."),
        }
        headline, subline = lines.get(self.cockpit_tab, lines["HOME"])
        painter.setFont(QFont("Consolas", max(11, int(w * 0.014)), QFont.Weight.Bold))
        painter.setPen(QColor(50, 255, 210, 235))
        painter.drawText(QRectF(rect.x(), rect.y() + 10, rect.width(), 30), Qt.AlignmentFlag.AlignCenter, headline)
        painter.setFont(QFont("Consolas", max(7, int(w * 0.007)), QFont.Weight.Bold))
        painter.setPen(QColor(150, 255, 228, 120))
        painter.drawText(QRectF(rect.x() + 8, rect.y() + rect.height() * 0.56, rect.width() - 16, 26), Qt.AlignmentFlag.AlignCenter, subline)

    def draw_cockpit_wave(self, painter, w, h):
        y = int(h * 0.92)
        painter.setPen(QPen(QColor(0, 255, 190, 90), 1))
        painter.drawLine(int(w * 0.05), y, int(w * 0.95), y)
        last = None
        amp_base = 18 + int(self.voice_energy * 55)
        for x in range(int(w * 0.05), int(w * 0.95), 4):
            wave = math.sin(x * 0.045 + self.pulse * 0.22) + math.sin(x * 0.018 + self.pulse * 0.09)
            height = int(wave * amp_base * (0.35 + self.voice_energy))
            point = QPoint(x, y + height)
            if last:
                painter.setPen(QPen(QColor(0, 255, 190, 120 + int(self.voice_energy * 110)), 1))
                painter.drawLine(last, point)
            last = point

    def draw_panel_frames(self, painter, w, h):
        def clipped_box(x, y, rw, rh, cut, glow=70):
            path = QPainterPath()
            path.moveTo(x + cut, y)
            path.lineTo(x + rw - cut, y)
            path.lineTo(x + rw, y + cut)
            path.lineTo(x + rw, y + rh - cut)
            path.lineTo(x + rw - cut, y + rh)
            path.lineTo(x + cut, y + rh)
            path.lineTo(x, y + rh - cut)
            path.lineTo(x, y + cut)
            path.closeSubpath()
            painter.fillPath(path, QColor(0, 5, 3, 110))
            painter.setPen(QPen(QColor(0, 255, 102, glow), 5))
            painter.drawPath(path)
            painter.setPen(QPen(QColor(0, 255, 102, 210), 1))
            painter.drawPath(path)
            painter.setPen(QPen(QColor(0, 255, 102, 120), 1))
            painter.drawLine(int(x + 10), int(y + 6), int(x + rw * 0.20), int(y + 6))
            painter.drawLine(int(x + rw * 0.80), int(y + rh - 6), int(x + rw - 10), int(y + rh - 6))

        margin = int(w * 0.075)
        clipped_box(margin - 5, int(h * 0.378), w - margin * 2 + 10, int(h * 0.255), 16)
        clipped_box(margin, int(h * 0.655), int(w * 0.55), 40, 7, glow=42)
        clipped_box(int(w * 0.64), int(h * 0.655), int(w * 0.29), 40, 11, glow=72)

    def draw_matrix_rain(self, painter, w, h, green):
        painter.setFont(QFont("Consolas", 6 if not self.cockpit_mode else 7, QFont.Weight.Bold))
        base_alpha = 54 if self.cockpit_mode and self.performance_mode else (82 if self.cockpit_mode else 135)
        fade_step = 7 if self.cockpit_mode and self.performance_mode else (5 if self.cockpit_mode else 6)
        for column in self.matrix_columns:
            x = int(column["x"])
            y = int(column["y"])
            char_step = 2 if self.cockpit_mode and self.performance_mode else 1
            for index in range(0, column["length"], char_step):
                char = column["chars"][index % len(column["chars"])]
                alpha = max(8, base_alpha - index * fade_step)
                if index == 0:
                    alpha = 100 if self.cockpit_mode and self.performance_mode else (150 if self.cockpit_mode else 210)
                painter.setPen(QColor(0, 255, 102, alpha))
                painter.drawText(x, y - index * 11, char)

        painter.setPen(QPen(QColor(0, 255, 102, 24), 1))
        painter.drawLine(0, self.scanline, w, self.scanline)

    def draw_core(self, painter, w, h, green, soft):
        cx = w // 2
        cy = int(h * 0.145)
        pulse = abs(90 - self.pulse) / 90
        painter.setPen(QPen(QColor(0, 255, 102, 32), 5))
        painter.drawEllipse(QPoint(cx, cy), 58, 58)
        painter.setPen(QPen(QColor(0, 255, 102, 70), 1))
        painter.drawLine(cx - int(w * 0.20), cy, cx - 34, cy)
        painter.drawLine(cx + 34, cy, cx + int(w * 0.20), cy)

        for i, radius in enumerate([15, 23, 32, 42, 53]):
            alpha = 45 + i * 26 + int(pulse * 40)
            painter.setPen(QPen(QColor(0, 255, 102, alpha), 1))
            painter.drawEllipse(QPoint(cx, cy), radius, radius)

        for angle in range(0, 360, 30):
            rad = math.radians(angle + self.pulse)
            r1, r2 = 43, 48
            x1 = cx + math.cos(rad) * r1
            y1 = cy + math.sin(rad) * r1
            x2 = cx + math.cos(rad) * r2
            y2 = cy + math.sin(rad) * r2
            painter.setPen(QPen(QColor(0, 255, 102, 105), 1))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        outer = QPainterPath()
        outer.moveTo(cx, cy - 21)
        outer.lineTo(cx - 20, cy + 15)
        outer.lineTo(cx + 20, cy + 15)
        outer.closeSubpath()
        painter.fillPath(outer, QColor(0, 255, 102, 16))
        painter.setPen(QPen(QColor(0, 255, 102, 230), 2))
        painter.drawPath(outer)
        inner = QPainterPath()
        inner.moveTo(cx, cy - 10)
        inner.lineTo(cx - 9, cy + 8)
        inner.lineTo(cx + 9, cy + 8)
        inner.closeSubpath()
        painter.setPen(QPen(QColor(0, 255, 102, 155), 1))
        painter.drawPath(inner)
        painter.setPen(QPen(QColor(0, 255, 102, 160), 1))
        painter.drawEllipse(QPoint(cx, cy), 8, 8)

    def draw_title(self, painter, w, h, green):
        text = "J.A.R.V.I.S"
        size = max(32, int(w * 0.125)) + int(self.voice_energy * 2)
        y = int(h * 0.215 + self.title_jitter)
        font = QFont("Impact", size, QFont.Weight.Black)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        while QFontMetrics(font).horizontalAdvance(text) > int(w * 0.80) and size > 26:
            size -= 1
            font = QFont("Impact", size, QFont.Weight.Black)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        painter.setFont(font)
        text_rect = QRectF(0, y - 5, w, 76)
        for width, alpha in [(18, 18), (12, 36), (7, 85), (3, 150)]:
            painter.setPen(QPen(QColor(0, 255, 102, alpha + int(self.voice_energy * 45)), width))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.setPen(QColor(0, 255, 82, 245))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.setPen(QPen(QColor(0, 5, 2, 90), 2))
        for line_y in range(int(y + 4), int(y + 58), 7):
            painter.drawLine(int(w * 0.14), line_y, int(w * 0.86), line_y)
        painter.setPen(QPen(QColor(0, 255, 102, 125), 1))
        painter.drawLine(int(w * 0.12), y + 48, int(w * 0.88), y + 48)
        painter.setPen(QPen(QColor(0, 255, 102, 55), 4))
        painter.drawLine(int(w * 0.20), y + 50, int(w * 0.80), y + 50)

    def draw_status_plate(self, painter, w, h, green):
        y = int(h * 0.335)
        plate = QPainterPath()
        plate.moveTo(w * 0.31, y)
        plate.lineTo(w * 0.69, y)
        plate.lineTo(w * 0.74, y + 13)
        plate.lineTo(w * 0.69, y + 26)
        plate.lineTo(w * 0.31, y + 26)
        plate.lineTo(w * 0.26, y + 13)
        plate.closeSubpath()
        painter.fillPath(plate, QColor(0, 42, 16, 170))
        painter.setPen(QPen(green, 1))
        painter.drawPath(plate)
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.drawText(QRectF(0, y + 4, w, 20), Qt.AlignmentFlag.AlignCenter, f"DURUM: {self.current_status}")

    def draw_wave(self, painter, w, h, green):
        y = int(h * 0.79)
        wave_alpha = 120 + int(self.voice_energy * 110)
        painter.setPen(QPen(QColor(0, 255, 102, wave_alpha), 1 + int(self.voice_energy * 2)))
        last = None
        for x in range(10, w - 10, 3):
            local = (x + self.pulse * (4 + self.voice_energy * 8)) % 80
            amp = abs(40 - local) / 40
            speech = math.sin((x * 0.08) + (self.pulse * 0.25)) * self.voice_energy
            height = int((1 - amp) * (24 + self.voice_energy * 42) + abs(speech) * 26)
            point = QPoint(x, y + height if x % 2 else y - height)
            if last:
                painter.drawLine(last, point)
            last = point

        cx = w // 2
        radius = 42 + int(self.voice_energy * 10)
        painter.setPen(QPen(QColor(0, 255, 102, 52), 8))
        painter.drawEllipse(QPoint(cx, y), radius + 8, radius + 8)
        painter.setPen(QPen(QColor(0, 255, 102, 120), 1))
        painter.drawEllipse(QPoint(cx, y), radius + 16, radius + 16)
        painter.setPen(QPen(green, 2 + int(self.voice_energy * 2)))
        painter.drawEllipse(QPoint(cx, y), radius, radius)
        painter.setPen(QPen(green, 3))
        mic_w = 14 + int(self.voice_energy * 4)
        mic_h = 28 + int(self.voice_energy * 7)
        painter.drawRoundedRect(QRectF(cx - mic_w / 2, y - mic_h / 2, mic_w, mic_h), 6, 6)
        painter.drawLine(cx, int(y + mic_h / 2), cx, int(y + mic_h / 2 + 10))
        painter.drawLine(cx - 11, int(y + mic_h / 2 + 10), cx + 11, int(y + mic_h / 2 + 10))
        painter.setFont(QFont("Consolas", 5, QFont.Weight.Bold))
        painter.drawText(QRectF(cx - 36, y + radius - 10, 72, 10), Qt.AlignmentFlag.AlignCenter, "MIKROFON: ACIK")
        return
        painter.setPen(QPen(QColor(0, 255, 102, 155), 1))
        last = None
        for x in range(10, w - 10, 3):
            local = (x + self.pulse * 4) % 80
            amp = abs(40 - local) / 40
            height = int((1 - amp) * 30)
            point = QPoint(x, y + height if x % 2 else y - height)
            if last:
                painter.drawLine(last, point)
            last = point

        cx = w // 2
        painter.setPen(QPen(green, 2))
        painter.drawEllipse(QPoint(cx, y), 38, 38)
        painter.setFont(QFont("Consolas", 24, QFont.Weight.Bold))
        painter.drawText(QRectF(cx - 28, y - 24, 56, 56), Qt.AlignmentFlag.AlignCenter, "🎙")

    def draw_footer(self, painter, w, h, green):
        # ESKİ → güncellendi
        y = h - 40
        bar_h = 32
        left_w = 188
        right_w = 88
        gap = 10
        center_x = left_w + gap
        center_w = max(82, w - left_w - right_w - gap * 3)
        right_x = w - right_w - 10

        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))

        def footer_box(rect, text, align=Qt.AlignmentFlag.AlignCenter):
            painter.fillRect(rect, QColor(0, 18, 8, 155))
            painter.setPen(QPen(QColor(0, 255, 102, 95), 1))
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QColor(0, 255, 102, 230))
            painter.drawText(rect.adjusted(8, 0, -8, 0), align | Qt.AlignmentFlag.AlignVCenter, text)

        footer_box(QRectF(center_x, y, center_w, bar_h), self.system_stats_text)
        footer_box(QRectF(right_x, y, right_w, bar_h), time.strftime("%H:%M"), Qt.AlignmentFlag.AlignCenter)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("J.A.R.V.I.S")
    # ESKİ → güncellendi
    window = JarvisUI(start_mini="--mini" in sys.argv, start_silent="--silent" in sys.argv)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
