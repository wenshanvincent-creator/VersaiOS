@echo off
"%~dp0.venv\Scripts\python.exe" "%~dp0tools\phone_open_app.py" %*
exit /b %errorlevel%
