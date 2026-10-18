@echo off
"%~dp0.venv\Scripts\python.exe" "%~dp0tools\phone_service.py"
exit /b %errorlevel%
