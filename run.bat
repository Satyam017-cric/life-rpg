@echo off
if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r requirements.txt
if "%SECRET_KEY%"=="" set SECRET_KEY=change-this-in-production
python app.py
