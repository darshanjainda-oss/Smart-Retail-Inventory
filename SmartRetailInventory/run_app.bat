@echo off
setlocal
cd /d "%~dp0"
title Smart Retail Inventory

echo ========================================
echo       SMART RETAIL INVENTORY
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python and make sure it is added to PATH.
    echo.
    pause
    exit /b 1
)

python --version
echo.
echo Starting the Flask application...
echo Keep this window open while using the application.
echo Open http://127.0.0.1:5000 in your browser.
echo.
python app.py

if errorlevel 1 (
    echo.
    echo The application stopped with an error. Check the message above.
)

echo.
pause
endlocal
