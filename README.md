# P50 Label Studio

Source und fertige EXE liegen im selben Ordner (`D:\github\Marklife P50 Windows`).
Es gibt drei Wege:

- `P50_Label_Studio.exe` starten – fertige App, nichts weiter noetig.
- `start.bat` starten – Source direkt nutzen, ohne EXE zu bauen (nutzt `.venv`
  und das lokale `chrome` aus diesem Ordner).
- `build.bat` ausfuehren – neu bauen; die fertige EXE wird wieder in diesen
  Ordner gelegt. Vorher die laufende EXE schliessen.

## Bauen

Nur diese Dateien werden benoetigt:

- `app.py`
- `index.html`
- `P50_Label_Studio.spec`
- `icon.png`
- `build_helper.py`
- `build.bat`
- `requirements-build.txt`
- `chrome-profile/.gitkeep`

`build.bat` installiert PyInstaller/pywin32/Pillow in einer lokalen `.venv`,
laedt Chrome for Testing stable (win64) automatisch herunter, erzeugt `icon.ico`
aus `icon.png` und legt die fertige EXE direkt in diesen Ordner:

```text
P50_Label_Studio.exe
```

Chrome startet ausserdem mit deaktivierter Desktop-Suche (`OmniboxEverywhere`),
deaktivierter Taskleisten-Suche, deaktiviertem globalen Such-Hotkey und
deaktiviertem Hintergrundmodus. Das verhindert auch das leere graue
Such-Fenster beim ersten Start.

Beim Start der EXE wird alles nach:

```text
%LOCALAPPDATA%\P50WebLabelStudio
```

entpackt. Chrome startet mit `--no-sandbox` (notwendig, damit die lokale
Seite in der EXE laedt) und den bentigten Web-Bluetooth-Flags als App-Fenster.
Ein einmaliges `Bluetooth verbinden` im Programm ist noetig, danach funktioniert
`Wiederherstellen` ohne Dialog.

## Bedienung

- Bilder einfach in die Vorschau ziehen (oder rechts die Datei auswaehlen).
- Bild-Griffe: Ecken aendern die Gesamtgroesse, Seitengriffe nur Breite oder
  Hoehe. Mit gedrueckter Umschalt-Taste bleibt die gegenueberliegende Seite
  feststehen.
- Unter der Vorschau: **Bild leeren**, **Inhalt anpassen (Hoehe)** und
  **Blatt leeren**.
- Textobjekte ueber die Icon-Leiste rechts: Das Schriftart-Icon (Aa) oeffnet
  eine Auswahl mit allen verfuegbaren Browser-/Systemschriften, ausserdem
  Groesse, Ausrichtung, Fett/Kursiv und Zeilenhöhe. Die Buttons wirken auf das
  ausgewählte Textobjekt, sonst auf den naechsten Text.
- Bluetooth-Funktionen liegen im **Bluetooth-Manager**: Verbinden,
  Wiederherstellen, Geraet loeschen, Trennen und ein Haken fuer automatische
  Verbindung.
- Protokoll, USB-Warteschlange, Raster-Kompression, Vorschub, langsame Sendung,
  Debug-Bytecodes sowie ESC/POS-Text-Test und „Nur Vorschub“ stehen unter
  **Erweiterte Optionen**. Die Debug-Bytecodes erscheinen nur, wenn dort der
  Haken gesetzt ist.
- Sprachumschaltung oben rechts in der Vorschau: 🇩🇪 DE / EN.
- Der Bluetooth-Status („Bluetooth verbunden“ bzw. „Bereit“) erscheint auch
  dann noch, wenn der Bluetooth-Manager minimiert ist.
