@echo off
REM Dive Report Generator Launcher
REM This batch file launches the enhanced dive report generator

echo.
echo ========================================
echo   Dive Report Generator - Enhanced
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not found in PATH
    echo Please install Python 3.7+ or add it to your PATH
    pause
    exit /b 1
)

echo Starting application...
echo.

REM Run the main script
python "%~dp0main.py"

if errorlevel 1 (
    echo.
    echo Application exited with an error
    pause
)
