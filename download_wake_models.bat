@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe download_wake_models.py
) else (
    py -3.12 download_wake_models.py
)
pause
