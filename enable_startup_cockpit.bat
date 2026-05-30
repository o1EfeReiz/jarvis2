@echo off
cd /d "%~dp0"
echo Cockpit baslangici devre disi birakildi. Tek JARVIS baslangici kuruluyor...
call "%~dp0install_jarvis_tasks.bat"
if errorlevel 1 pause
exit /b %ERRORLEVEL%
