@echo off
cd /d "%~dp0"
if not exist .venv (
    echo First run: creating environment and installing libraries...
    py -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
.venv\Scripts\python.exe -m streamlit run app.py
