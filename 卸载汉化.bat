@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title Wrench Chinese Patch - Uninstall
set "PY="
for %%P in ("py -3" "%USERPROFILE%\miniconda3\python.exe" "%USERPROFILE%\anaconda3\python.exe" "python") do (
  if not defined PY (
    %%~P -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul && set "PY=%%~P"
  )
)
if not defined PY (
  echo Python 3.8+ not found.
  echo To uninstall by hand, delete zzz_WrenchZhCN_P.pak from:
  echo   ...\steamapps\common\Wrench\WindowsNoEditor\WrenchGame\Content\Paks
  pause
  exit /b 1
)
%PY% tools\build.py --uninstall %*
pause
endlocal
