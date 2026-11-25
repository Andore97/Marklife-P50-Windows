@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PY="

echo [1/5] Python suchen ...
for %%V in (3.12 3.11 3.10 3.9) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  python -c "import sys" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo FEHLER: Python nicht gefunden. Bitte Python 3.9+ installieren.
  exit /b 1
)
echo   gefunden: !PY!

echo [2/5] Build-Umgebung vorbereiten ...
if not exist ".venv\Scripts\python.exe" (
  !PY! -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 exit /b 1

echo [3/5] Chrome stable + Icon vorbereiten ...
".venv\Scripts\python.exe" build_helper.py
if errorlevel 1 exit /b 1

echo [4/5] EXE bauen ...
if exist "dist\P50_Label_Studio.exe" del /f /q "dist\P50_Label_Studio.exe"
".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm P50_Label_Studio.spec --distpath dist --workpath build
if errorlevel 1 exit /b 1
if not exist "dist\P50_Label_Studio.exe" (
  echo FEHLER: EXE wurde nicht erstellt.
  exit /b 1
)

echo [5/5] EXE in diesen Ordner kopieren ...
tasklist /FI "IMAGENAME eq P50_Label_Studio.exe" 2>nul | find /I "P50_Label_Studio.exe" >nul
if not errorlevel 1 (
  echo FEHLER: P50_Label_Studio.exe laeuft noch. Bitte zuerst schliessen.
  exit /b 1
)
copy /Y "dist\P50_Label_Studio.exe" "P50_Label_Studio.exe" >nul
if errorlevel 1 exit /b 1

echo.
echo FERTIG: %~dp0P50_Label_Studio.exe
echo.
endlocal
