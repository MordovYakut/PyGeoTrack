@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Окружение не найдено. Установите Python 3.11 или 3.12 и выполните:
  echo py -m venv .venv
  echo .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python main.py
if errorlevel 1 pause
