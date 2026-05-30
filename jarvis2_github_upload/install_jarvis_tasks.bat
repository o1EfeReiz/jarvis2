@echo off
cd /d "%~dp0"
set "BASE=%~dp0"
set "STARTUP_TASK=JarvisStartup"
set "BACKUP_TASK=JarvisDailyBackup"

echo Eski JARVIS baslangic kayitlari temizleniyor...
schtasks /Delete /F /TN "JarvisStartup" >nul 2>nul
schtasks /Delete /F /TN "JARVIS Startup" >nul 2>nul
schtasks /Delete /F /TN "JarvisDailyBackup" >nul 2>nul
schtasks /Delete /F /TN "JARVIS Daily Backup" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.bat" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.vbs" >nul 2>nul

echo JARVIS Task Scheduler gorevleri kuruluyor...
schtasks /Create /F /TN "%STARTUP_TASK%" /SC ONLOGON /RL LIMITED /TR "wscript.exe ""%BASE%run_jarvis_task.vbs"""
if errorlevel 1 goto failed

schtasks /Create /F /TN "%BACKUP_TASK%" /SC DAILY /ST 03:00 /RL LIMITED /TR "cmd.exe /c ""%BASE%run_jarvis_backup.bat"""
if errorlevel 1 goto failed

echo.
echo JARVIS Startup ve Daily Backup gorevleri kuruldu.
echo Startup: kullanici oturum actiginda mini/sessiz baslar.
echo Backup: her gun 03:00'de C:\jarvis_v2\backups klasorune yedek alir.
exit /b 0

:failed
echo.
echo Gorev kurulumunda hata olustu. PowerShell/CMD'yi yonetici olarak acip tekrar dene.
exit /b 1
