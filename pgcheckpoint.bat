@echo off
chcp 65001 >nul 2>&1
title PostgreSQL Checkpoint Manager

where python >nul 2>&1
if %errorlevel%==0 (
    python "%~dp0pgcheckpoint.py"
    pause
    exit /b
)

if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" "%~dp0pgcheckpoint.py"
    pause
    exit /b
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" "%~dp0pgcheckpoint.py"
        pause
        exit /b
    )
)

echo.
echo [ERRO] Python nao encontrado.
echo Instale o Python em https://www.python.org/downloads/
echo.
pause
