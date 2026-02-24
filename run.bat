@echo off
cd /d "%~dp0"

echo ========================================
echo   SmartID Ecosystem - Web Server
echo ========================================
echo.

REM Run migrations if needed
python manage.py migrate --run-syncdb

echo.
echo Starting server at http://127.0.0.1:8000
echo Press Ctrl+C to stop.
echo.

python manage.py runserver
