@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title Wrench Chinese Patch - Install

echo [1/3] Checking for updates (git pull)...
where git >nul 2>nul
if errorlevel 1 (
  echo   git not found, skipping update check.
) else (
  git pull --ff-only origin main
  if errorlevel 1 echo   git pull failed, continuing with local files.
)

echo [2/3] Looking for Python 3...
set "PY="
for %%P in ("py -3" "%USERPROFILE%\miniconda3\python.exe" "%USERPROFILE%\anaconda3\python.exe" "python") do (
  if not defined PY (
    %%~P -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul && set "PY=%%~P"
  )
)
if not defined PY (
  echo   Python 3.8+ not found. Please install it from https://www.python.org/ and run again.
  pause
  exit /b 1
)
echo   Using: %PY%

echo [3/3] Building the patch from your game files and installing it...
%PY% tools\build.py --install %*
if errorlevel 1 (
  echo.
  echo   FAILED. See the message above.
  pause
  exit /b 1
)

echo.
choice /c YN /m "Launch Wrench now"
if errorlevel 2 goto :done
start "" "steam://rungameid/936720"
:done
endlocal
