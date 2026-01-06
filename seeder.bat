@echo off
cd /d "%~dp0"

IF NOT EXIST "env" (
    echo Virtual environment 'env' not found.
    echo Please run 'run.bat' first to set up the environment.
    pause
    exit /b 1
)

call env\Scripts\activate

echo Running seeder...
python seeder.py

echo Seeding completed.
pause
