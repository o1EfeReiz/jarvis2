@echo off
cd /d "%~dp0"
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 bulunamadi.
    echo Lutfen https://www.python.org/downloads/release/python-31210/ adresinden Python 3.12 kur.
    echo Kurarken "Add Python to PATH" kutusunu isaretle.
    pause
    exit /b 1
)
py -3.12 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
echo.
echo Kurulum bitti. Calistirmak icin run_jarvis.bat dosyasina cift tikla.
pause
