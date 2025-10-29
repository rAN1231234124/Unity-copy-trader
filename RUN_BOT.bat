@echo off
echo ============================================================
echo Unity Copy Trader - Bot Launcher
echo ============================================================
echo.

:menu
echo Choose which version to run:
echo.
echo 1. Stable Version (neil_bot_stable.py) - Recommended
echo 2. Original Version (neil_bot.py)
echo 3. Run with Monitor (auto-restart on crash)
echo 4. Exit
echo.

set /p choice=Enter your choice (1-4):

if "%choice%"=="1" goto stable
if "%choice%"=="2" goto original
if "%choice%"=="3" goto monitor
if "%choice%"=="4" goto end

echo Invalid choice! Please try again.
goto menu

:stable
echo.
echo Starting STABLE version...
echo ============================================================
python neil_bot_stable.py
pause
goto menu

:original
echo.
echo Starting ORIGINAL version...
echo ============================================================
python neil_bot.py
pause
goto menu

:monitor
echo.
echo Starting with AUTO-RESTART monitor...
echo This will keep the bot running 24/7
echo Press Ctrl+C to stop
echo ============================================================
python monitor_bot.py
pause
goto menu

:end
echo.
echo Goodbye!
exit