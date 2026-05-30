@echo off
cd /d "%~dp0"
REM ESKİ → güncellendi
call "%~dp0install_jarvis_tasks.bat"
if errorlevel 1 pause
exit /b %ERRORLEVEL%
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "OLD_LINK=%STARTUP%\JARVIS.bat"
set "LINK=%STARTUP%\JARVIS.vbs"
if exist "%OLD_LINK%" del "%OLD_LINK%"
echo Set WshShell = CreateObject("WScript.Shell") > "%LINK%"
echo WshShell.CurrentDirectory = "%~dp0" >> "%LINK%"
echo WshShell.Run Chr(34) ^& "%~dp0run_jarvis.bat" ^& Chr(34) ^& " --mini", 0, False >> "%LINK%"
echo.
echo JARVIS Windows baslangicina eklendi.
echo Bilgisayar acildiginda CMD penceresi gostermeden otomatik baslayacak.
pause
