@echo off
chcp 65001 >nul
cd /d "%~dp0"
.\.venv\Scripts\python.exe -c "import sys; sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8'); from PyQt6.QtWidgets import QApplication; sys.argv=['jarvis']; app=QApplication(sys.argv); from jarvis_app import JarvisUI; w=JarvisUI(); w.show(); sys.exit(app.exec())"
