import datetime as dt
import os
import shutil
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BACKUP_ROOT = Path(r"C:\jarvis_v2\backups")
KEEP_DAYS = 7

PLAIN_FILES = [
    "jarvis_app.py",
    "jarvis_memory.json",
    "jarvis_changelog.txt",
    "coords.json",
]


def write_log(level, message):
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}\n"
    with (BASE_DIR / "jarvis_log.txt").open("a", encoding="utf-8") as handle:
        handle.write(line)


def encrypt_env(source, destination):
    if not source.exists():
        return False

    command = (
        "$plain = Get-Content -Raw -LiteralPath $env:JARVIS_ENV_SOURCE; "
        "$secure = ConvertTo-SecureString $plain -AsPlainText -Force; "
        "$secure | ConvertFrom-SecureString | Set-Content -LiteralPath $env:JARVIS_ENV_DEST"
    )
    env = os.environ.copy()
    env["JARVIS_ENV_SOURCE"] = str(source)
    env["JARVIS_ENV_DEST"] = str(destination)
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        check=True,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    readme = destination.with_suffix(destination.suffix + ".README.txt")
    readme.write_text(
        "Bu dosya Windows DPAPI ile mevcut kullanici hesabina bagli olarak sifrelendi.\n"
        "Cozmek icin ayni Windows kullanicisi ve bilgisayar gerekir.\n",
        encoding="utf-8",
    )
    return True


def prune_old_backups():
    if not BACKUP_ROOT.exists():
        return
    folders = [path for path in BACKUP_ROOT.iterdir() if path.is_dir()]
    folders.sort(key=lambda item: item.name, reverse=True)
    for old_folder in folders[KEEP_DAYS:]:
        shutil.rmtree(old_folder, ignore_errors=True)
        write_log("BACKUP", f"Eski yedek silindi: {old_folder}")


def main():
    today = dt.datetime.now().strftime("%Y-%m-%d")
    target = BACKUP_ROOT / today
    target.mkdir(parents=True, exist_ok=True)

    copied = []
    skipped = []
    for name in PLAIN_FILES:
        source = BASE_DIR / name
        if source.exists():
            shutil.copy2(source, target / name)
            copied.append(name)
        else:
            skipped.append(name)

    encrypted = False
    try:
        encrypted = encrypt_env(BASE_DIR / ".env", target / ".env.encrypted.txt")
    except Exception as exc:
        write_log("HATA", f".env sifreli yedeklenemedi: {exc}")

    prune_old_backups()

    details = ", ".join(copied) if copied else "kopyalanan dosya yok"
    if encrypted:
        details += ", .env sifreli"
    if skipped:
        details += f" | eksik: {', '.join(skipped)}"
    write_log("BACKUP", f"Yedek tamamlandi: {target} | {details}")
    print(f"JARVIS backup tamamlandi: {target}")


if __name__ == "__main__":
    main()
