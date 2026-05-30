@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe jarvis_backup.py
    exit /b %ERRORLEVEL%
)
py -3.12 jarvis_backup.py
