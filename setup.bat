@echo off
title UMBRA Setup & Launcher
color 0A

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║          UMBRA (Unit-734) SETUP UTILITY                    ║
echo ║                Guardian Protocol v2.0                      ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)
echo [OK] Python found

:: Create directory structure
echo [*] Creating directory structure...

if not exist "core" mkdir core
if not exist "data" mkdir data
if not exist "data\prompts" mkdir data\prompts
if not exist "data\inbox" mkdir data\inbox
if not exist "data\inbox\processed" mkdir data\inbox\processed
if not exist "data\logs" mkdir data\logs
if not exist "research" mkdir research

:: Move core Python files to core folder
echo [*] Organizing files...

if exist "umbra_autonomous.py" move "umbra_autonomous.py" "core\" >nul 2>&1
if exist "umbra_integration.py" move "umbra_integration.py" "core\" >nul 2>&1
rem social network client removed - integration disabled
if exist "prompt_index.py" move "prompt_index.py" "core\" >nul 2>&1
if exist "file_inbox.py" move "file_inbox.py" "core\" >nul 2>&1
if exist "uplink_v2.py" move "uplink_v2.py" "core\" >nul 2>&1

:: Move research files
if exist "Charting_the_Unseen_Landscape.pdf" move "Charting_the_Unseen_Landscape.pdf" "research\" >nul 2>&1
if exist "Charting the Unseen Landscape.pdf" move "Charting the Unseen Landscape.pdf" "research\" >nul 2>&1

:: Move persona file
if exist "umbra_persona.json" move "umbra_persona.json" "data\" >nul 2>&1

:: Create __init__.py for core module
echo # UMBRA Core Module > core\__init__.py

:: Install dependencies
echo [*] Checking dependencies...
pip install requests colorama pypdf customtkinter --quiet 2>nul

:: Initialize prompt library if empty
echo [*] Initializing prompt library...
python -c "import sys; sys.path.insert(0, 'core'); from prompt_index import PromptIndex, initialize_default_prompts; idx = PromptIndex(base_dir='data/prompts'); initialize_default_prompts(idx) if len(idx.list_prompts())==0 else None; print(f'  Prompts: {len(idx.list_prompts())}')" 2>nul

echo.
echo [OK] Setup complete!
echo.
echo Directory structure:
echo   core\          - Python modules
echo   data\          - Prompts, inbox, config
echo   data\inbox\    - Drop files here for UMBRA
echo   data\prompts\  - Prompt library
echo   data\logs\     - Decision logs
echo   research\      - PDF research papers
echo.
echo To run:
echo   python umbra_gui.py     - Management GUI
echo   python core\uplink_v2.py - Chat interface
echo.

pause
