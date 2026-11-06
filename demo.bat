@echo off
rem Starts the dashboard with live simulation through WSL. Needs WSL2 with Ubuntu 24.04, see README.md.
where wsl >nul 2>nul
if errorlevel 1 (
  echo WSL is not installed. Open dashboard.html for the recorded results, or see README.md for the WSL setup.
  pause
  exit /b 1
)
wsl --cd "%~dp0." -- bash run_demo.sh
pause
