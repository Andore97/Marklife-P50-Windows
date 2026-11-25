@echo off
cd /d "%~dp0"
echo Starte P50 Web Label Studio direkt aus der Source ...
echo Halte dieses Fenster offen. Chrome oeffnet sich automatisch.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
) else (
  python app.py
)
pause
