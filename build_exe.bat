@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Окружение .venv не найдено.
  echo Создайте его и установите зависимости из requirements-lock.txt.
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install "PySide6==6.8.3" "pyinstaller>=6.10,<7"
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean PyGeoTrack.spec
if errorlevel 1 exit /b 1

echo Готово: dist\PyGeoTrack.exe
