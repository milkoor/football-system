@echo off
chcp 65001 >nul
title Football System - Starting
echo ========================================
echo Starting Football Betting System...
echo ========================================
echo.

cd /d "%~dp0"

echo Building Docker images...
call docker-compose build

echo.
echo Starting services...
call docker-compose up -d

echo.
echo Waiting for services...
echo.

rem Wait for database
echo -n   Database...
:wait_db
ping -n 2 127.0.0.1 >nul
docker inspect --format="{{.State.Health.Status}}" football_system_db 2>nul | findstr "healthy" >nul
if errorlevel 1 goto wait_db
echo OK

rem Wait for system A
echo -n   System A (API)...
:wait_a
ping -n 2 127.0.0.1 >nul
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 goto wait_a
echo OK

rem Wait for system B
echo -n   System B (Frontend)...
:wait_b
ping -n 2 127.0.0.1 >nul
curl -s http://localhost:8501/_stcore/health >nul 2>&1
if errorlevel 1 goto wait_b
echo OK

echo.
echo ========================================
echo Done! System started successfully!
echo ========================================
echo.
echo Access URLs:
echo    System A API:   http://localhost:8000
echo    System B UI:    http://localhost:8501
echo    PostgreSQL:     localhost:5432
echo.
echo Commands:
echo    View logs:   docker-compose logs -f
echo    Stop:        stop.bat
echo    Status:      status.bat
echo ========================================
pause