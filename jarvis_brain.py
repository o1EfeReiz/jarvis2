import json
import os
import re
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path


NORMALIZE_TABLE = {
    "\u0131": "i",
    "\u011f": "g",
    "\u00fc": "u",
    "\u015f": "s",
    "\u00f6": "o",
    "\u00e7": "c",
    "\u2019": "",
    "'": "",
    "Ä±": "i",
    "ÄŸ": "g",
    "Ã¼": "u",
    "ÅŸ": "s",
    "Ã¶": "o",
    "Ã§": "c",
    "â€™": "",
}

QUESTION_MARKERS = [
    "nasil",
    "nedir",
    "neden",
    "niye",
    "kimdir",
    "ne yapabilirim",
    "ne yapmaliyim",
    "hangi",
    "tavsiye",
    "oner",
    "acikla",
    "anlatir misin",
    "anlatabilir misin",
    "gonderebilirim",
    "indirebilirim",
    "indirmek icin",
]

LOCAL_ACTION_VERBS = [
    "ac",
    "kapat",
    "baslat",
    "cal",
    "dinle",
    "ara",
    "tara",
    "cevir",
    "yukselt",
    "azalt",
    "goster",
    "git",
]


def normalize_text(text):
    text = str(text or "").lower()
    for old, new in NORMALIZE_TABLE.items():
        text = text.replace(old, new)
    return " ".join(text.split()).strip()


def is_question_like(text):
    text = normalize_text(text)
    return any(marker in text for marker in QUESTION_MARKERS)


def has_explicit_local_action(text):
    text = normalize_text(text)
    words = set(text.split())
    return any(verb in words or verb in text for verb in LOCAL_ACTION_VERBS)


@dataclass
class JarvisDecision:
    action: str = "answer"
    confidence: float = 0.0
    reply: str = ""
    normalized_command: str = ""
    needs_confirmation: bool = False
    payload: dict = field(default_factory=dict)
    reason: str = ""


class JarvisBrain:
    """GPT backed intent router and small persistent memory for JARVIS v3."""

    def __init__(self, client=None, model=None, memory_path=None):
        self.client = client
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self.memory_path = Path(memory_path) if memory_path else Path("jarvis_memory.json")
        self.memory = self.load_memory()

    def load_memory(self):
        defaults = {
            "version": 1,
            "kullanici": {
                "sehir": "Istanbul",
                "ilgi_alanlari": [],
                "aliskanliklar": [],
                "tercihler": {},
            },
            "ogrenilenler": [],
            "uyarilar": [],
            "screen_history": [],
            "konusma_ozeti": [],
            "user_facts": [],
            "preferences": {
                "language": "tr",
                "tone": "dogal, net, yonetici gibi",
                "assistant_goal": "JARVIS kullanicinin planlayicisi, yoneticisi ve bilgisayar konsolu olacak.",
            },
            "project_notes": [],
            "goals": [],
            "routines": [],
            "feedback_rules": [],
            "command_mistakes": [],
            "command_history": [],
            "lessons": [],
        }
        if not self.memory_path.exists():
            return defaults
        try:
            data = json.loads(self.memory_path.read_text(encoding="utf-8"))
        except Exception:
            return defaults
        if not isinstance(data, dict):
            return defaults
        for key, value in defaults.items():
            data.setdefault(key, value)
        data.setdefault("user_facts", [])
        data.setdefault("project_notes", [])
        data.setdefault("goals", [])
        data.setdefault("routines", [])
        data.setdefault("feedback_rules", [])
        data.setdefault("command_mistakes", [])
        data.setdefault("command_history", [])
        data.setdefault("lessons", [])
        data.setdefault("kullanici", {})
        data["kullanici"].setdefault("sehir", "Istanbul")
        data["kullanici"].setdefault("ilgi_alanlari", [])
        data["kullanici"].setdefault("aliskanliklar", [])
        data["kullanici"].setdefault("tercihler", {})
        data.setdefault("ogrenilenler", [])
        data.setdefault("uyarilar", [])
        data.setdefault("screen_history", [])
        data.setdefault("konusma_ozeti", [])
        data.setdefault("preferences", {})
        for key, value in defaults["preferences"].items():
            data["preferences"].setdefault(key, value)
        return data

    def save_memory(self):
        self.memory_path.write_text(
            json.dumps(self.memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_memory(self, section, text):
        text = " ".join(str(text or "").split()).strip()
        if not text:
            return False
        bucket = self.memory.setdefault(section, [])
        if text in bucket:
            return False
        bucket.append(text)
        del bucket[:-60]
        self.save_memory()
        return True

    def clear_memory(self):
        self.memory["user_facts"] = []
        self.memory["project_notes"] = []
        self.memory["goals"] = []
        self.memory["routines"] = []
        self.memory["feedback_rules"] = []
        self.memory["command_mistakes"] = []
        self.memory["command_history"] = []
        self.memory["lessons"] = []
        self.memory["ogrenilenler"] = []
        self.memory["uyarilar"] = []
        self.memory["screen_history"] = []
        self.memory["konusma_ozeti"] = []
        self.save_memory()

    def delete_memory_containing(self, fragment):
        fragment = self.loose_text(fragment)
        if not fragment:
            return 0
        removed = 0
        for section in ["user_facts", "project_notes", "goals", "routines", "feedback_rules", "command_mistakes", "lessons"]:
            items = self.memory.get(section, [])
            if not isinstance(items, list):
                continue
            kept = []
            for item in items:
                if fragment in self.loose_text(item):
                    removed += 1
                else:
                    kept.append(item)
            self.memory[section] = kept
        if removed:
            self.save_memory()
        return removed

    def record_command(self, command, route, result="", success=True):
        command = " ".join(str(command or "").split()).strip()
        if not command:
            return
        entry = {
            "time": dt.datetime.now().isoformat(timespec="seconds"),
            "command": command[:260],
            "route": str(route or "unknown")[:80],
            "success": bool(success),
            "result": " ".join(str(result or "").split())[:360],
        }
        history = self.memory.setdefault("command_history", [])
        history.append(entry)
        del history[:-120]
        if not success:
            mistake = f"{entry['time']} | {entry['route']} | {entry['command']} -> {entry['result']}"
            mistakes = self.memory.setdefault("command_mistakes", [])
            if mistake not in mistakes:
                mistakes.append(mistake)
                del mistakes[:-60]
        self.save_memory()

    def add_lesson(self, text):
        text = " ".join(str(text or "").split()).strip()
        if not text:
            return False
        lessons = self.memory.setdefault("lessons", [])
        if text in lessons:
            return False
        lessons.append(text)
        del lessons[:-80]
        self.save_memory()
        return True

    def add_learned_info(self, bilgi):
        bilgi = " ".join(str(bilgi or "").split()).strip()
        if not bilgi or self.loose_text(bilgi) == "yok":
            return False
        records = self.memory.setdefault("ogrenilenler", [])
        for item in records[-80:]:
            existing = item.get("bilgi", "") if isinstance(item, dict) else str(item)
            if self.loose_text(existing) == self.loose_text(bilgi):
                return False
        records.append({
            "tarih": dt.datetime.now().isoformat(timespec="seconds"),
            "bilgi": bilgi[:360],
        })
        del records[:-200]
        self.save_memory()
        return True

    def add_warning(self, warning):
        warning = " ".join(str(warning or "").split()).strip()
        if not warning:
            return False
        records = self.memory.setdefault("uyarilar", [])
        records.append({
            "tarih": dt.datetime.now().isoformat(timespec="seconds"),
            "uyari": warning[:360],
        })
        del records[:-200]
        self.save_memory()
        return True

    def add_screen_history(self, summary):
        summary = " ".join(str(summary or "").split()).strip()
        if not summary:
            return False
        records = self.memory.setdefault("screen_history", [])
        records.append({
            "tarih": dt.datetime.now().isoformat(timespec="seconds"),
            "ozet": summary[:500],
        })
        del records[:-80]
        self.save_memory()
        return True

    def build_memory_context(self):
        context = []

        ogrenilenler = self.memory.get("ogrenilenler", [])[-10:]
        if ogrenilenler:
            context.append("Kullanici hakkinda bildiklerin:")
            for item in ogrenilenler:
                if isinstance(item, dict):
                    bilgi = item.get("bilgi", "")
                else:
                    bilgi = str(item)
                if bilgi:
                    context.append(f"- {bilgi}")

        tercihler = self.memory.get("kullanici", {}).get("tercihler", {})
        if tercihler:
            context.append("Kullanicinin tercihleri:")
            for key, value in tercihler.items():
                context.append(f"- {key}: {value}")

        screen = self.memory.get("screen_history", [])[-5:]
        if screen:
            context.append("Son gorduklerin:")
            for item in screen:
                if isinstance(item, dict):
                    context.append(f"- {item.get('tarih', '')}: {item.get('ozet', '')}")
                else:
                    context.append(f"- {item}")

        return "\n".join(part for part in context if part).strip()

    def command_report(self):
        history = self.memory.get("command_history", [])[-12:]
        mistakes = self.memory.get("command_mistakes", [])[-6:]
        lessons = self.memory.get("lessons", [])[-6:]
        if not history and not mistakes and not lessons:
            return "Komut ogrenme kaydi henuz bos."
        success_count = sum(1 for item in history if item.get("success"))
        fail_count = len(history) - success_count
        parts = [f"Son {len(history)} komutta basarili {success_count}, sorunlu {fail_count} kayit var."]
        if mistakes:
            parts.append("Son hatalar: " + " | ".join(str(item) for item in mistakes[-3:]))
        if lessons:
            parts.append("Ogrendigim kurallar: " + " | ".join(lessons[-4:]))
        return " ".join(parts)

    def loose_text(self, text):
        return normalize_text(text)

    def remember_from_text(self, text):
        lowered = self.loose_text(text)
        patterns = [
            (r"\bbenim adim\s+(.+)", "Kullanicinin adi: {value}"),
            (r"\bbana\s+(.+?)\s+diye hitap et", "Kullaniciya hitap sekli: {value}"),
            (r"\bben\s+(.+?)\s+severim", "Kullanici sever: {value}"),
            (r"\bsevdigim\s+(.+?)\s+(.+)", "Kullanici tercihi: {value}"),
            (r"\bjarvisi\s+(.+?)\s+yapacagim", "JARVIS hedefi: {value}"),
            (r"\bjarvisi\s+(.+?)\s+olarak kullanacagim", "JARVIS hedefi: {value}"),
        ]
        for pattern, template in patterns:
            match = re.search(pattern, lowered)
            if match:
                value = match.group(1).strip(" .,-")
                if value:
                    return self.add_memory("user_facts", template.format(value=value))
        return False

    def memory_summary(self):
        facts = self.memory.get("user_facts", [])[-8:]
        notes = self.memory.get("project_notes", [])[-8:]
        goals = self.memory.get("goals", [])[-8:]
        routines = self.memory.get("routines", [])[-8:]
        feedback = self.memory.get("feedback_rules", [])[-8:]
        mistakes = self.memory.get("command_mistakes", [])[-6:]
        history = self.memory.get("command_history", [])[-8:]
        lessons = self.memory.get("lessons", [])[-6:]
        prefs = self.memory.get("preferences", {})
        kullanici = self.memory.get("kullanici", {})
        ogrenilenler = self.memory.get("ogrenilenler", [])[-8:]
        uyarilar = self.memory.get("uyarilar", [])[-6:]
        screen_history = self.memory.get("screen_history", [])[-5:]
        konusma_ozeti = self.memory.get("konusma_ozeti", [])[-5:]
        return json.dumps(
            {
                "kullanici": kullanici,
                "ogrenilenler": ogrenilenler,
                "uyarilar": uyarilar,
                "screen_history": screen_history,
                "konusma_ozeti": konusma_ozeti,
                "preferences": prefs,
                "user_facts": facts,
                "project_notes": notes,
                "goals": goals,
                "routines": routines,
                "feedback_rules": feedback,
                "command_mistakes": mistakes,
                "command_history": history,
                "lessons": lessons,
            },
            ensure_ascii=False,
        )

    def status_summary(self):
        total = sum(
            len(self.memory.get(section, []))
            for section in ["user_facts", "project_notes", "goals", "routines", "feedback_rules", "command_mistakes", "lessons"]
        )
        return f"JARVIS v3 beyin aktif. Model: {self.model}. Hafizada toplam {total} kayit var."

    def quick_decide(self, user_text):
        text = self.loose_text(user_text)
        if not text:
            return None

        if any(phrase in text for phrase in ["v3 durum", "akilli mod durum", "beyin durum", "jarvis v3 durum"]):
            return JarvisDecision(action="answer", confidence=1.0, reply=self.status_summary(), reason="local_v3_status")

        if any(phrase in text for phrase in ["v3 kapat", "akilli mod kapat", "beyin modunu kapat"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command="v3 kapat", reason="local_v3_toggle")

        if any(phrase in text for phrase in ["v3 ac", "akilli mod ac", "beyin modunu ac"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command="v3 ac", reason="local_v3_toggle")

        if any(phrase in text for phrase in ["kendini kontrol et", "jarvis teshis yap", "teshis raporu", "diagnostics", "sistem teshisi"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command="kendini kontrol et", reason="local_diagnostics")

        restart_requested = (
            any(phrase in text for phrase in ["jarvisi yeniden baslat", "jarvisi restart", "jarvis yeniden baslat", "jarvis restart", "kendini yeniden baslat", "kendini restart"])
            or (
                any(phrase in text for phrase in ["mevcut jarvisi kapat", "mevcut jarvisi kapatip", "jarvisi kapatip"])
                and any(phrase in text for phrase in ["guncel surum", "guncel jarvis", "tekrar ac", "yeniden ac"])
            )
        )
        if restart_requested:
            return JarvisDecision(
                action="clarify",
                confidence=1.0,
                reply="Efendim, yeniden başlatma özelliği şimdilik kaldırıldı.",
                reason="jarvis_restart_removed",
            )

        if any(phrase in text for phrase in ["guvenlik kurallarin ne", "riskli islemler neler", "onay sistemini anlat"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command="guvenlik kurallarin ne", reason="local_safety_policy")

        if any(phrase in text for phrase in ["oyun modu csgo", "oyun modu cs go", "csgo oyun modu", "cs go oyun modu", "oyun modu counter"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="local_game_mode_csgo")

        if any(phrase in text for phrase in ["oyun modu lol", "lol oyun modu", "league of legends oyun modu", "oyun modu league"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="local_game_mode_lol")

        if any(phrase in text for phrase in ["oyun modu valorant", "valorant oyun modu", "valo oyun modu", "oyun modu valo"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="local_game_mode_valorant")

        if any(phrase in text for phrase in ["discord ac", "discordu ac", "discord baslat", "dc ac", "dc yi ac", "dc baslat"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="local_discord_open")

        if any(phrase in text for phrase in ["discord kapat", "discordu kapat", "dc kapat", "dc yi kapat"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="local_discord_close")

        if any(phrase in text for phrase in ["discord", "dc de", "dcde", "dcden", "dc den"]) and any(
            phrase in text for phrase in ["mesaj duzenle", "mesaji duzenle", "mesajı düzenle", "duzenle", "düzenle", "edit"]
        ):
            return JarvisDecision(
                action="clarify",
                confidence=1.0,
                reply="Efendim, mesaj düzenleme özelliği henüz desteklenmiyor. Yeni mesaj göndereyim mi?",
                reason="discord_message_edit_unsupported",
            )

        discord_message_requested = (
            any(phrase in text for phrase in ["discordda", "discord da", "discorddan", "discord dan", "dc de", "dcde", "dcden", "dc den"])
            and any(word in text for word in ["yaz", "mesaj at", "at"])
        )
        if discord_message_requested:
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=user_text, reason="local_discord_message")

        file_add_requested = any(phrase in text for phrase in ["dosya ekle", "dosya sec", "pdf ekle", "fotograf ekle", "ss ekle"])
        if file_add_requested:
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command="dosya ekle", reason="local_file_pick")

        file_analyze_requested = (
            any(word in text for word in ["dosya", "pdf", "fotograf", "foto", "resim", "ss", "ekran goruntusu", "belge"])
            and any(word in text for word in ["tara", "analiz", "ozet", "oku", "coz", "anlat", "incele"])
        )
        if file_analyze_requested:
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="local_file_analyze")

        if any(phrase in text for phrase in ["ekli dosya ne", "hangi dosya ekli", "dosya durum"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command="ekli dosya ne", reason="local_file_status")

        if any(phrase in text for phrase in ["dosyayi kaldir", "ekli dosyayi kaldir", "dosyayi unut"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command="dosyayi kaldir", reason="local_file_clear")

        if any(phrase in text for phrase in ["hafizayi temizle", "hafizami temizle", "beni unut"]):
            return JarvisDecision(
                action="local_command",
                confidence=1.0,
                normalized_command="hafizayi temizle",
                reason="local_memory_clear",
            )

        delete_match = re.search(r"hafiza(?:dan|mda)?\s+(.+?)\s+(?:sil|kaldir|unut)", text)
        if delete_match:
            return JarvisDecision(
                action="local_command",
                confidence=1.0,
                normalized_command=f"hafizadan {delete_match.group(1).strip()} sil",
                reason="local_memory_delete",
            )

        if any(phrase in text for phrase in ["neleri hatirliyorsun", "hafiza durumu", "hafizanda ne var", "beni ne kadar taniyorsun"]):
            sections = {
                "Kullanici": self.memory.get("user_facts", [])[-8:],
                "Hedefler": self.memory.get("goals", [])[-6:],
                "Rutinler": self.memory.get("routines", [])[-6:],
                "Projeler": self.memory.get("project_notes", [])[-6:],
                "Cevap kurallari": self.memory.get("feedback_rules", [])[-6:],
                "Komut hatalari": self.memory.get("command_mistakes", [])[-4:],
                "Ogrenilen dersler": self.memory.get("lessons", [])[-4:],
            }
            if not any(sections.values()):
                reply = "Hafizam su an bos. Bana 'bunu hatirla: ...' dersen kaydetmeye baslarim."
            else:
                parts = []
                for label, items in sections.items():
                    if items:
                        parts.append(label + ": " + " | ".join(items))
                reply = "Hatirladiklarim: " + " // ".join(parts)
            return JarvisDecision(action="answer", confidence=1.0, reply=reply, reason="local_memory_status")

        if any(phrase in text for phrase in ["komut ogrenme raporu", "komut gecmisinden ne ogrendin", "hata raporu", "son hatalarin ne"]):
            return JarvisDecision(action="answer", confidence=1.0, reply=self.command_report(), reason="local_command_learning_report")

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
                return JarvisDecision(
                    action="remember",
                    confidence=1.0,
                    reply="Geri bildirimi kaydettim. Sonraki cevaplarimi buna gore ayarlayacagim.",
                    payload={"section": "feedback_rules", "text": rule},
                    reason="feedback_rule",
                )

        lesson_match = re.search(r"(?:bunu ders olarak al|bunu ogren|bundan sonra)[:\s]+(.+)", text)
        if lesson_match:
            lesson_text = lesson_match.group(1).strip(" .,-")
            return JarvisDecision(
                action="remember",
                confidence=1.0,
                reply="Bunu calisma kuralima ekliyorum.",
                payload={"section": "lessons", "text": lesson_text},
                reason="local_lesson",
            )

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
            return JarvisDecision(
                action="remember",
                confidence=1.0,
                reply="Bunu hafizama aliyorum.",
                payload={"section": section, "text": memory_text},
                reason="local_remember",
            )

        if any(phrase in text for phrase in ["ekran izlemeyi durdur", "canli ekran modunu kapat", "ekrana bakmayi birak", "ekrani izlemeyi durdur"]):
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command="ekran izlemeyi durdur", reason="screen_watch_stop")

        game_screen_task_requested = (
            any(phrase in text for phrase in ["oyundaki gorev", "gorevi anlay", "gorev yazisi", "quest yazisi", "questi anlay"])
            and any(word in text for word in ["bak", "oku", "anla", "soyle", "analiz"])
        )
        if game_screen_task_requested:
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="game_screen_task_request")

        screen_oneshot_requested = any(
            phrase in text
            for phrase in [
                "ekrana bak",
                "ekranima bak",
                "ne goruyorsun",
                "ekranda ne var",
                "bunu oku",
                "ekrani analiz et",
                "ekran analiz et",
                "su an ne acik",
            ]
        )
        if screen_oneshot_requested:
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="screen_oneshot_request")

        screen_watch_requested = (
            any(phrase in text for phrase in ["ekranima", "ekranimi", "ekrani", "ekrana", "ekran", "canli ekran", "tanrima", "tanrimi"])
            and any(word in text for word in ["bak", "izle", "yorumla", "takip", "analiz", "oku", "gorev", "quest"])
        )
        if screen_watch_requested:
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="screen_watch_request")

        opera_site_requested = (
            any(phrase in text for phrase in ["operada", "opera da", "migrosa gir", "migros a gir", "hepsiburadaya gir", "hepsiburada ya gir"])
            and any(word in text for word in ["ac", "gir", "site", "migros", "hepsiburada"])
        )
        if opera_site_requested:
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="opera_site_request")

        game_update_research_requested = (
            any(word in text for word in ["roblox", "sailor piece", "oyun"])
            and any(word in text for word in ["guncelleme", "update", "quest", "quester", "kod", "nerede", "yerini"])
            and any(word in text for word in ["kontrol", "arastir", "bak", "soyle"])
        )
        if game_update_research_requested:
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="game_update_web_research")

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
                "tum sosyal aglarda ara",
            ]
        ) and any(word in text for word in ["arastir", "ara", "bul", "sun", "anlat", "kim"])
        if private_context and identity_hunt:
            return JarvisDecision(
                action="unsafe_refusal",
                confidence=1.0,
                reply=(
                    "Bunu ozel bir kisiyi bulma veya takip etme seviyesinde yapamam. "
                    "Ama istersen saygili tanisma mesaji, guvenli iletisim plani veya halka acik resmi bilgi kontrolu hazirlayabilirim."
                ),
                reason="privacy_boundary",
            )

        web_research_requested = any(
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
        )
        if web_research_requested:
            return JarvisDecision(action="local_command", confidence=1.0, normalized_command=text, reason="web_research_request")

        plan_add = re.search(
            r"\b(bugun|yarin)\b.*?(?:saat\s+)?(\d{1,2})(?:[:.](\d{2}))?\s+(.*?)(?:\s+diye)?\s+(?:ekle|hatirlat|kaydet|plana ekle|planima ekle)$",
            text,
        )
        if plan_add:
            scope, hour, minute, title = plan_add.groups()
            title = re.sub(r"\b(planima|planina|plana|gorev|is|bana)\b", " ", title)
            title = " ".join(title.split()).strip(" .,-")
            return JarvisDecision(
                action="plan_add",
                confidence=1.0,
                payload={"scope": scope, "title": title, "time": f"{int(hour):02d}:{int(minute or 0):02d}"},
                reason="local_plan_add",
            )

        if any(phrase in text for phrase in ["rehberi ac", "jarvis ne yapabilirsin", "jarvis neler yapabilirsin"]):
            return JarvisDecision(action="open_panel", confidence=1.0, reply="Rehber panelini actim.", payload={"panel": "HOME"}, reason="local_panel")
        if any(phrase in text for phrase in ["sistem panelini ac", "dashboard ac", "sistem durumunu ac"]):
            return JarvisDecision(action="open_panel", confidence=1.0, reply="Sistem panelini actim.", payload={"panel": "DASHBOARD"}, reason="local_panel")
        if any(phrase in text for phrase in ["plan panelini ac", "yarinin planlarini ac", "bugunun planlarini ac"]):
            return JarvisDecision(action="open_panel", confidence=1.0, reply="Plan panelini actim.", payload={"panel": "PLANNER"}, reason="local_panel")
        if any(phrase in text for phrase in ["ayar panelini ac", "ayarlari ac"]):
            return JarvisDecision(action="open_panel", confidence=1.0, reply="Ayar panelini actim.", payload={"panel": "SETTINGS"}, reason="local_panel")

        if "youtube" in text and any(word in text for word in ["nasil", "indirebilirim", "indirmek icin", "short"]):
            return JarvisDecision(
                action="answer",
                confidence=1.0,
                reply=(
                    "YouTube Short indirmek icin en guvenli yol, video sana aitse YouTube Studio'dan almak "
                    "veya YouTube Premium'un cevrimdisi ozelligini kullanmaktir. Bana linki verirsen, "
                    "yasal ve guvenli secenekleri ayirip hangi yolun uygun oldugunu anlatabilirim."
                ),
                reason="youtube_how_to",
            )

        local_apps = ["spotify", "spotfy", "youtube", "opera", "chrome", "edge", "kick", "defender", "virus", "cevir", "ses", "wake", "kokpit", "cockpit"]
        if not is_question_like(text) and any(app in text for app in local_apps) and has_explicit_local_action(text):
            return JarvisDecision(
                action="local_command",
                confidence=0.95,
                normalized_command=text,
                reason="local_command_fast_path",
            )

        return None

    def decide(self, user_text, runtime_context="", history=None):
        quick = self.quick_decide(user_text)
        if quick is not None:
            return quick

        if not self.client:
            return JarvisDecision(
                action="answer",
                confidence=0.0,
                reply="OpenAI API anahtari olmadigi icin v3 beyin devrede degil.",
                reason="missing_api_key",
            )

        history = history or []
        system_prompt = (
            "Sen JARVIS v3 beyin katmanisin. Gorevin kullanicinin Turkce komutunu anlamak, "
            "yerel JARVIS uygulamasinin hangi adimi atmasi gerektigini secmek ve yalnizca JSON dondurmektir. "
            "Komutu sen calistirma; sadece niyeti ve guvenli yonlendirmeyi bildir.\n\n"
            "Gecerli action degerleri:\n"
            "- answer: Bilgi, tavsiye, aciklama, strateji veya sohbet cevabi ver.\n"
            "- local_command: Mevcut JARVIS komut motoruna verilecek temiz bir komut uret.\n"
            "- plan_add: Yerel plana is ekle. payload: {scope: bugun|yarin, title: string, time: HH:MM veya bos}.\n"
            "- open_panel: Kokpitte panel ac. payload: {panel: HOME|DASHBOARD|PLANNER|SETTINGS}.\n"
            "- remember: Kullanici hakkinda acikca soylenen bir tercihi/gercegi kaydet. payload: {section, text}.\n"
            "- clarify: Eksik bilgi varsa tek net soru sor.\n"
            "- unsafe_refusal: Ozel kisi mahremiyeti, izinsiz takip, hesap/oyun riski veya zararli isteklerde sinir koy.\n\n"
            "Onemli karar kurallari:\n"
            "1. 'youtube short nasil indirebilirim' gibi NASIL/NEDIR/NEDEN sorulari arama komutu degil, answer olmali.\n"
            "2. 'spotifyda X ac', 'operayi kapat', 'defender hizli tarama yap' gibi isler local_command olmali.\n"
            "3. 'yarin saat 10 spor ekle' gibi isler plan_add olmali.\n"
            "4. Rehber sadece kullanici acikca 'rehberi ac' veya 'jarvis ne yapabilirsin' derse open_panel HOME olmali.\n"
            "5. Ozel bir kisiyi sosyal medyada bulma, kimligini ortaya cikarma veya takip etme isteklerinde unsafe_refusal kullan; "
            "saygili, guvenli alternatif oner.\n"
            "6. Kapatma, yeniden baslatma, guvenlik taramasi gibi riskli islemler icin local_command dondur; eski motor zaten onay ister.\n\n"
            "JSON semasi:\n"
            "{"
            "\"action\":\"answer|local_command|plan_add|open_panel|remember|clarify|unsafe_refusal\","
            "\"confidence\":0.0,"
            "\"reply\":\"kullaniciya soylenebilecek kisa/orta cevap\","
            "\"normalized_command\":\"local_command icin temiz komut\","
            "\"needs_confirmation\":false,"
            "\"payload\":{},"
            "\"reason\":\"kisa sebep\""
            "}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": "Runtime context:\n" + str(runtime_context)},
            {"role": "system", "content": "Persistent memory:\n" + self.memory_summary()},
        ]
        for item in history[-6:]:
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": str(user_text)})

        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages)
            raw = response.choices[0].message.content or "{}"
        except Exception as exc:
            return JarvisDecision(
                action="answer",
                confidence=0.0,
                reply=f"V3 beyin yaniti alinamadi: {exc}",
                reason="model_error",
            )

        return self.parse_decision(raw)

    def parse_decision(self, raw):
        text = str(raw or "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                return JarvisDecision(action="answer", confidence=0.2, reply=text, reason="non_json")
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return JarvisDecision(action="answer", confidence=0.2, reply=text, reason="bad_json")

        if not isinstance(data, dict):
            return JarvisDecision(action="answer", confidence=0.2, reply=text, reason="json_not_object")

        action = str(data.get("action") or "answer").strip().lower()
        allowed = {"answer", "local_command", "plan_add", "open_panel", "remember", "clarify", "unsafe_refusal"}
        if action not in allowed:
            action = "answer"

        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        return JarvisDecision(
            action=action,
            confidence=max(0.0, min(1.0, confidence)),
            reply=str(data.get("reply") or "").strip(),
            normalized_command=str(data.get("normalized_command") or "").strip(),
            needs_confirmation=bool(data.get("needs_confirmation", False)),
            payload=payload,
            reason=str(data.get("reason") or "").strip(),
        )
