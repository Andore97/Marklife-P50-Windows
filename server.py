#!/usr/bin/env python3
"""Lokaler RAW-Druck-Brief fuer den Marklife P50.

Dient die index.html aus (Bluetooth laeuft im Browser, nicht hier) und schickt den fertigen Byte-Stream per
win32print mit Datatype RAW direkt an die Windows-Druckerwarteschlange.
Damit werden GDI-Skalierung und Treiber-Transformationen umgangen.
"""

import json
import os
import subprocess
import threading
import webbrowser
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import win32print

HOST = "127.0.0.1"
PORT = 8765
ROOT = Path(__file__).resolve().parent
PREFERRED = ("P50 Printer", "P50 Printer (1)")


def open_in_chrome(url):
    """Startet Chrome (portabel in chrome/ oder installiert) mit eigenem Profil in chrome-profile/."""
    candidates = [ROOT / "chrome" / "chrome.exe",
                  ROOT / "chrome" / "chrome-win64" / "chrome.exe",
                  Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe"]
    for exe in candidates:
        if exe.exists():
            subprocess.Popen([str(exe), f"--user-data-dir={ROOT / 'chrome-profile'}",
                              "--no-first-run", "--no-default-browser-check", f"--app={url}"])
            return True
    webbrowser.open(url)
    return False


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
            # Tab/Browser wurde waehrend der Antwort geschlossen.
            self.close_connection = True

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.respond(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
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
                if wbits not in (9, 10, 11, 12, 13, 14, 15, -9, -10, -11, -12, -13, -14, -15):
                    raise ValueError("ungueltiges wbits")
                co = zlib.compressobj(level, zlib.DEFLATED, wbits)
                payload = co.compress(raw) + co.flush()
                self.respond(200, payload, "application/octet-stream")
                return

            name = request.get("printer") or printer_names()[0]
            payload = bytes.fromhex(request.get("dataHex", "").replace(" ", ""))
            copies = max(1, min(int(request.get("copies", 1)), 20))
            for _ in range(copies):
                raw_print(name, payload)
            result = {"ok": True, "printer": name, "bytes": len(payload), "copies": copies}
            self.respond(200, json.dumps(result).encode())
        except Exception as exc:
            self.respond(500, json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode())

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"P50 Web UI: http://{HOST}:{PORT}")
    print("Gefundene Warteschlangen:", ", ".join(printer_names()) or "(keine)")
    print("Bluetooth: laeuft komplett im Browser (Web Bluetooth), Python haelt keine BLE-Verbindung.")
    threading.Timer(0.8, lambda: open_in_chrome(f"http://{HOST}:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
