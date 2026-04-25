@echo off
echo Starting Discord Anti-Impersonator Bot...

:: Check if virtual environment exists
if not exist venv\Scripts\activate.bat (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Install or update requirements
echo Installing requirements...
pip install -r requirements.txt

:: Run the bot
echo Running bot...
python bot.py

pause
