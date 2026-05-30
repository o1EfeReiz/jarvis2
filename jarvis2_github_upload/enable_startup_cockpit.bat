@echo off
cd /d "%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "OLD_LINK=%STARTUP%\JARVIS.bat"
set "LINK=%STARTUP%\JARVIS.vbs"
if exist "%OLD_LINK%" del "%OLD_LINK%"
echo Set WshShell = CreateObject("WScript.Shell") > "%LINK%"
echo WshShell.CurrentDirectory = "%~dp0" >> "%LINK%"
echo WshShell.Run Chr(34) ^& "%~dp0run_jarvis.bat" ^& Chr(34) ^& " --cockpit", 0, False >> "%LINK%"
echo.
echo JARVIS Windows baslangicina cockpit modu ile eklendi.
echo Bilgisayar acildiginda CMD penceresi gostermeden ikinci ekranda buyuk panel olarak baslamayi dener.
pause
