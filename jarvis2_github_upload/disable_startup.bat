@echo off
REM ESKİ → güncellendi
call "%~dp0remove_jarvis_tasks.bat"
set "LINK_BAT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.bat"
set "LINK_VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.vbs"
set "REMOVED=0"
if exist "%LINK_BAT%" (
    del "%LINK_BAT%"
    set "REMOVED=1"
)
if exist "%LINK_VBS%" (
    del "%LINK_VBS%"
    set "REMOVED=1"
)
if "%REMOVED%"=="1" (
    echo JARVIS Windows baslangicindan kaldirildi.
) else (
    echo Baslangicta JARVIS kaydi bulunamadi.
)
pause
