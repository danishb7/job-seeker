@echo off
title Job Seeker
cd /d "%~dp0"
python run_server.py
if errorlevel 1 (
  echo.
  echo If you saw "python is not recognized", install Python from python.org
  echo and check "Add python.exe to PATH", then try again.
  pause
)
