@echo off
schtasks /Delete /F /TN "JarvisStartup" >nul 2>nul
schtasks /Delete /F /TN "JarvisDailyBackup" >nul 2>nul
schtasks /Delete /F /TN "JARVIS Startup" >nul 2>nul
schtasks /Delete /F /TN "JARVIS Daily Backup" >nul 2>nul
schtasks /Delete /F /TN "JarvisCockpitStartup" >nul 2>nul
schtasks /Delete /F /TN "JARVIS Cockpit Startup" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.bat" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.vbs" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS_COCKPIT.bat" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS_COCKPIT.vbs" >nul 2>nul
echo JARVIS Task Scheduler gorevleri kaldirildi.
