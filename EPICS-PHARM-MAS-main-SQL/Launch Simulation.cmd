@echo off
setlocal
rem Double-click to open the four-drawer desktop app in simulation mode.
rem No hardware, password, network access or Raspberry Pi is contacted.
title Starting Pharmacy Drawer (simulation)
echo Starting Pharmacy Drawer in simulation mode...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" -Detached
if errorlevel 1 (
    echo.
    echo Launch failed. See the message above and docs\RUNNING.md.
    pause
)
