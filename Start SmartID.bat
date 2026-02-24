@echo off
title SmartID Ecosystem
cd /d "%~dp0"

REM Start Django server in a separate window (uses system Python, no venv)
start "SmartID Server" cmd /k "cd /d "%~dp0" && python manage.py runserver"

REM Wait for server to be ready, then open browser
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:8000/"
