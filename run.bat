@echo off
cd /d "%~dp0"

IF NOT EXIST "env" (
    echo Creating virtual environment...
    python -m venv env
    call env\Scripts\activate
    echo Installing requirements...
    pip install -r requirements.txt
) ELSE (
    call env\Scripts\activate
)

echo Starting FastAPI server...
uvicorn main:app --reload
