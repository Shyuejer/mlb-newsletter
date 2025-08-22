@echo off
REM Activate venv
call venv-mlb-newsletter\Scripts\activate.bat

REM Run main.py
python main.py

REM Keep window open (optional)
pause