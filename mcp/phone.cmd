@echo off
"%~dp0.venv\Scripts\python.exe" "%~dp0tools\phone_macro.py" %*
exit /b %errorlevel%
