@echo off
chcp 65001 >nul
title Football System - Status
cd /d "%~dp0"
echo ========================================
echo System Status
echo ========================================
echo.
call docker-compose ps

echo.
echo ========================================
echo Service Health Check
echo ========================================

rem Check system A
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [FAIL] System A API: Not running
) else (
    echo [OK]   System A API: http://localhost:8000
)

rem Check system B
curl -s http://localhost:8501/_stcore/health >nul 2>&1
if errorlevel 1 (
    echo [FAIL] System B UI: Not running
) else (
    echo [OK]   System B UI: http://localhost:8501
)

rem Check database
docker inspect --format="{{.State.Health.Status}}" football_system_db 2>nul | findstr "healthy" >nul
if errorlevel 1 (
    echo [FAIL] PostgreSQL: Not running
) else (
    echo [OK]   PostgreSQL: localhost:5432
)

echo ========================================
pause