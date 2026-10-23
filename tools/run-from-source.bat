@echo off
rem Developer helper: start the window straight from the source tree (needs Python 3 with Pillow: python -m pip install pillow).
rem The release package does not use this: people double-click CapitalConvert.exe.
setlocal
cd /d "%~dp0.."
where pyw >nul 2>nul
if %errorlevel%==0 (
  start "" pyw -3 "builder\capital_builder.py"
  exit /b 0
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "builder\capital_builder.py"
  exit /b 0
)
echo Python 3 was not found on PATH.
pause
exit /b 1
