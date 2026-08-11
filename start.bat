@echo off
cd /d "%~dp0"
python server\run_server.py
if errorlevel 1 pause
