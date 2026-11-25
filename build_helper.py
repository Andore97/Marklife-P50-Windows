#!/usr/bin/env python3
"""Build-Helfer fuer P50 Label Studio.

Laedt Chrome for Testing (stable/win64), erzeugt das EXE-Icon aus icon.png
und legt ein leeres Chrome-Profil an. Danach kann PyInstaller die EXE bauen.
"""

import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
CHROME_DIR = ROOT / "chrome"
DOWNLOAD_DIR = ROOT / "chrome-downloads"
PROFILE_DIR = ROOT / "chrome-profile"
ICON_PNG = ROOT / "icon.png"
ICON_ICO = ROOT / "icon.ico"
VERSION_FILE = ROOT / "chrome_version.txt"

CF_TESTING_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)


def log(msg):
    print(msg, flush=True)


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "p50-label-studio-build"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def stable_chrome():
    data = fetch_json(CF_TESTING_URL)
    stable = data["channels"]["Stable"]
    version = stable["version"]
    for entry in stable["downloads"]["chrome"]:
        if entry.get("platform") == "win64":
            return version, entry["url"]
    raise RuntimeError("Kein Chrome-for-Testing-Download fuer win64 gefunden.")


def chrome_exe():
    for rel in ("chrome.exe", "chrome-win64/chrome.exe"):
        candidate = CHROME_DIR / rel
        if candidate.exists():
            return candidate
    return None


def download(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    if partial.exists():
        partial.unlink()
    log(f"Lade Chrome herunter: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "p50-label-studio-build"})
    with urllib.request.urlopen(req, timeout=180) as response, partial.open("wb") as out:
        shutil.copyfileobj(response, out, length=1024 * 1024)
    partial.replace(target)


def extract(zip_path):
    log("Entpacke Chrome ...")
    if CHROME_DIR.exists():
        shutil.rmtree(CHROME_DIR)
    CHROME_DIR.mkdir(parents=True)

    root = CHROME_DIR.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            prefix = "chrome-win64/"
            if not name.startswith(prefix):
                continue
            rel = name[len(prefix):]
            if not rel:
                continue
            target = (CHROME_DIR / rel).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError(f"Unsafe Pfad im Chrome-Zip: {name}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)


def prepare_chrome():
    version, url = stable_chrome()
    current = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else ""
    exe = chrome_exe()

    if current == version and exe is not None:
        log(f"Chrome {version} ist bereits aktuell – kein Download noetig.")
        return version

    DOWNLOAD_DIR.mkdir(exist_ok=True)
    zip_path = DOWNLOAD_DIR / f"chrome-win64-{version}.zip"
    if not zip_path.exists() or zip_path.stat().st_size < 50_000_000:
        download(url, zip_path)
    extract(zip_path)

    exe = chrome_exe()
    if exe is None:
        raise RuntimeError("chrome.exe fehlt nach dem Entpacken.")
    VERSION_FILE.write_text(version, encoding="utf-8")
    log(f"Chrome {version} bereit: {exe}")
    return version


def prepare_icon():
    candidates = [ICON_PNG, ROOT / "build" / "P50_Label_Studio" / "icon.png"]
    source = next((path for path in candidates if path.exists()), None)
    if source is None:
        raise FileNotFoundError("icon.png fehlt im Source-Root oder in build/P50_Label_Studio.")

    if source != ICON_PNG:
        shutil.copy2(source, ICON_PNG)

    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.save(
            ICON_ICO,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    log(f"Icon bereit: {ICON_ICO}")


def prepare_profile():
    PROFILE_DIR.mkdir(exist_ok=True)
    keep = PROFILE_DIR / ".gitkeep"
    if not keep.exists():
        keep.write_text("", encoding="utf-8")
    log(f"Profil bereit: {PROFILE_DIR}")


def main():
    prepare_icon()
    prepare_profile()
    prepare_chrome()
    log("Build-Vorbereitung fertig.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
