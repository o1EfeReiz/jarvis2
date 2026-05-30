@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        .venv\Scripts\python.exe jarvis_app.py %*
        if not errorlevel 1 exit /b 0
    )
    echo.
    echo .venv calismadi veya eski Python yoluna bagli, sistem Python deneniyor...
)
py -3.12 jarvis_app.py %*
if errorlevel 1 (
    echo.
    echo Once setup_jarvis.bat dosyasini calistir.
    pause
)
