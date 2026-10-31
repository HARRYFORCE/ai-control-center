@echo off
rem AI Control Center launcher (Windows): starts the bridge if needed, then opens the dashboard
rem in its own address-bar-free window. Put a shortcut to this file on your desktop or in shell:startup.
rem Window position / size / fullscreen: edit the three lines below (or ask your AI to do it).
setlocal
cd /d "%~dp0"
set "PORT=8790"
set "WINPOS=0,0"
set "WINSIZE=1360,1300"
set "FULLSCREEN="
rem set "FULLSCREEN=--start-fullscreen"   <- remove "rem" to open full screen (e.g. on a side monitor)
set "URL=http://127.0.0.1:%PORT%/"

rem 1) bridge: skip if it already answers
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%URL%' | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto browser
where pythonw >nul 2>&1
if errorlevel 1 (
  start "AI Control Center bridge" /min python bridge.py --port %PORT%
) else (
  start "" pythonw bridge.py --port %PORT%
)
powershell -NoProfile -Command "for ($i = 0; $i -lt 30; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 '%URL%' | Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 300 } }; exit 1" >nul 2>&1
if errorlevel 1 (
  echo The bridge did not start. Run "python bridge.py" in this folder to see the error.
  pause
  exit /b 1
)

:browser
rem 2) browser: Chrome, then Edge. A separate profile folder makes --window-position work
rem    even when your normal Chrome is already open (otherwise Chrome ignores it).
set "BROWSER="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "BROWSER=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not defined BROWSER if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not defined BROWSER (
  start "" "%URL%"
  exit /b 0
)
start "" "%BROWSER%" --app=%URL% --user-data-dir="%LocalAppData%\AIControlCenterApp" --window-position=%WINPOS% --window-size=%WINSIZE% %FULLSCREEN% --autoplay-policy=no-user-gesture-required
endlocal
