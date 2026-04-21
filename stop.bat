@echo off
chcp 65001 >nul
title Football System - Stop
cd /d "%~dp0"
echo Stopping services...
call docker-compose down
echo Done! All services stopped.
pause