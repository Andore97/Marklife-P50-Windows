#!/usr/bin/env python3
"""P50 Web Label Studio – Einzelne EXE mit portablem Chrome.

Beim Start wird alles nach %LOCALAPPDATA%\\P50WebLabelStudio entpackt,
danach startet Chrome mit den benoetigten Web-Bluetooth-Flags als App-Fenster.
Der Python-Server lebt nur so lange wie dieses Chrome-Fenster.
"""

import ctypes
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zlib
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import win32print

APP_NAME = "P50WebLabelStudio"
FALLBACK_VERSION = "1.0.0"
HOST = "127.0.0.1"
PORT = 8765
PREFERRED = ("P50 Printer", "P50 Printer (1)")

# PyInstaller --onefile startet einen Child-Prozess. Wenn der sichtbare
# Bootloader-Prozess vom User beendet wird, muss der Child mitsterben.
PARENT_PID = os.getppid()
chrome_process = None

CHROME_FLAGS = [
    # In dieser portablen EXE lädt Chrome ohne --no-sandbox keine lokale Seite.
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-search-engine-choice-screen",
    "--disable-background-mode",
    # "Suche vom Desktop aus" / Taskleiste / globaler Hotkey / Hintergrund
    "--disable-features=OmniboxEverywhere,OmniboxEverywhereFre,OmniboxEverywhereDeferStatusIcon",
    # Bleibt als Profil-Prefs zusätzlich deaktiviert (siehe disable_chrome_extras).
    "--enable-experimental-web-platform-features",
    "--enable-features=WebBluetoothNewPermissionsBackend",
    "--enable-blink-features=WebBluetoothGetDevices,WebBluetoothWatchAdvertisements",
]


def bundle_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def app_dir():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


def bundled_version():
    """Vom Build-Helper erzeugt – so wird bei Chrome-Updates neu entpackt."""
    try:
        return (bundle_dir() / "chrome_version.txt").read_text(encoding="utf-8").strip() or FALLBACK_VERSION
    except Exception:
        return FALLBACK_VERSION


def message_box(text):
    try:
        ctypes.windll.user32.MessageBoxW(0, text, "P50 Web Label Studio", 0x10)
    except Exception:
        pass


def merge_json_file(path, updates):
    """Prefs ergaenzen, ohne vorhandene Chrome-Einstellungen zu überschreiben."""
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        data = {}

    def merge(target, source):
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                merge(target[key], value)
            else:
                target[key] = value

    merge(data, updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def disable_chrome_extras(profile):
    """Deaktiviert Desktop-Suche, Taskleisten-Suche, Hotkey und Hintergrundmodus."""
    omnibox = {
        "enabled": False,
        "hotkey_enabled": False,
        "background_mode": False,
        "launch_on_startup": False,
        "fre_dismissed": True,
    }
    common = {
        "background_mode": {"enabled": False},
        "omnibox_everywhere": omnibox,
        "browser": {
            "has_seen_welcome_page": True,
            "has_seen_search_engine_choice_screen": True,
        },
        "profile": {"exit_type": "Normal", "exited_cleanly": True},
    }
    merge_json_file(profile / "Local State", common)
    merge_json_file(profile / "Default" / "Preferences", common)


def prepare_files():
    root = app_dir()
    root.mkdir(parents=True, exist_ok=True)
    src = bundle_dir()
    version_file = root / "version.txt"
    old = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else ""
    version = bundled_version()
    if old != version:
        shutil.copytree(src / "chrome", root / "chrome", dirs_exist_ok=True)
        version_file.write_text(version, encoding="utf-8")
    # Profil nur einmal anlegen – dort liegen die Bluetooth-Berechtigungen.
    profile = root / "chrome-profile"
    if not profile.exists():
        bundled_profile = src / "chrome-profile"
        if bundled_profile.exists():
            shutil.copytree(bundled_profile, profile)
        else:
            profile.mkdir(parents=True)
    shutil.copy2(src / "index.html", root / "index.html")
    # Chrome verwirft beim allerersten Profilstart manchmal die App-URL und
    # zeigt eine leere Seite. Der Marker beendet den First-Run-Pfad sauber.
    (profile / "First Run").touch()
    disable_chrome_extras(profile)
    return root


def printer_names():
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    names = {item[2] for item in win32print.EnumPrinters(flags)}
    return sorted(names, key=lambda n: (PREFERRED.index(n) if n in PREFERRED else 99, n))


def raw_print(name, payload):
    handle = win32print.OpenPrinter(name, {"DesiredAccess": win32print.PRINTER_ACCESS_ADMINISTER})
    try:
        doc = win32print.StartDocPrinter(handle, 1, ("P50 Web Raw", None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, payload)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def respond(self, code, body, ctype="application/json; charset=utf-8"):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            self.close_connection = True

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.respond(200, (app_dir() / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/printers":
            self.respond(200, json.dumps(printer_names()).encode())
        elif self.path == "/health":
            self.respond(200, b'{"ok":true}')
        else:
            self.respond(404, b'{"error":"not found"}')

    def do_POST(self):
        if self.path not in ("/print", "/compress"):
            self.respond(404, b'{"error":"not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            request = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/compress":
                raw = bytes.fromhex(request.get("dataHex", "").replace(" ", ""))
                level = max(0, min(int(request.get("level", 6)), 9))
                wbits = int(request.get("wbits", 10))
                co = zlib.compressobj(level, zlib.DEFLATED, wbits)
                self.respond(200, co.compress(raw) + co.flush(), "application/octet-stream")
                return
            name = request.get("printer") or printer_names()[0]
            payload = bytes.fromhex(request.get("dataHex", "").replace(" ", ""))
            copies = max(1, min(int(request.get("copies", 1)), 20))
            for _ in range(copies):
                raw_print(name, payload)
            self.respond(200, json.dumps({
                "ok": True, "printer": name, "bytes": len(payload), "copies": copies
            }).encode())
        except Exception as exc:
            self.respond(500, json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode())

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def log_message(self, fmt, *args):
        pass


# --- Prozess-Kopplung: Chrome stirbt mit der EXE und umgekehrt -----------------

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def assign_chrome_job(process):
    """KILL_ON_JOB_CLOSE: wenn die EXE stirbt, sterben Chrome und seine Kinder."""
    kernel = ctypes.windll.kernel32
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    try:
        kernel.AssignProcessToJobObject(job, int(process._handle))
    except Exception:
        pass
    return job


def parent_alive(pid):
    """Windows meldet die PPID nach dem Tod des Parents oft noch alt – Handle pruefen."""
    if not pid:
        return True
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if handle:
        exit_code = ctypes.c_ulong()
        ok = kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        kernel.CloseHandle(handle)
        return bool(ok) and exit_code.value == 259  # STILL_ACTIVE
    return False


def watch_parent():
    """EXE beendet -> Chrome und Child-Prozess beenden."""
    global chrome_process
    while True:
        time.sleep(0.7)
        if not parent_alive(PARENT_PID):
            try:
                if chrome_process is not None and chrome_process.poll() is None:
                    chrome_process.terminate()
            except Exception:
                pass
            os._exit(1)


def main():
    global chrome_process
    root = prepare_files()
    chrome = root / "chrome" / "chrome.exe"
    profile = root / "chrome-profile"
    if not chrome.exists():
        message_box("Chrome fehlt: " + str(chrome))
        return 1

    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as exc:
        message_box("Port " + str(PORT) + " ist belegt. Laeuft schon eine Instanz?\n" + str(exc))
        return 1

    threading.Thread(target=server.serve_forever, daemon=True).start()
    # Chrome erst starten, wenn der Server wirklich antwortet – sonst zeigt
    # das App-Fenster beim ersten Start nur eine Fehlerseite an.
    url = f"http://{HOST}:{PORT}/health"
    for _ in range(50):
        try:
            with urllib.request.urlopen(url, timeout=0.2) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.1)
    args = [str(chrome), f"--user-data-dir={profile}", *CHROME_FLAGS,
            f"--app=http://{HOST}:{PORT}/"]
    process = None
    job = None
    try:
        process = subprocess.Popen(args)
        chrome_process = process
        job = assign_chrome_job(process)
        threading.Thread(target=watch_parent, daemon=True).start()
        process.wait()
    finally:
        chrome_process = None
        server.shutdown()
        server.server_close()
        if process is not None and process.poll() is None:
            process.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
