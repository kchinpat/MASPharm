@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1" -Usb
if errorlevel 1 (
    echo.
    echo Launch failed. See docs\RUNNING.md.
    pause
)
