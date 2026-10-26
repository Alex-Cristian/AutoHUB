@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Lipseste mediul virtual .venv. Urmeaza instalarea din README.md.
    pause
    exit /b 1
)
echo Site: http://127.0.0.1:8000/
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
if errorlevel 1 pause
