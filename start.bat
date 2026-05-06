@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%\src
python -m rl_live_tracker
if errorlevel 1 pause
