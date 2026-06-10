@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

rem Use: pgcheckpoint.bat        -> abre a interface grafica (sem terminal)
rem      pgcheckpoint.bat --cli  -> abre o menu no terminal

echo %* | findstr /C:"--cli" >nul 2>&1
if not errorlevel 1 goto cli

rem === Modo GUI: pythonw nao abre janela de console ===

where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw -m pgcheckpoint
    exit /b
)

if exist "%LOCALAPPDATA%\Python\bin\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Python\bin\pythonw.exe" -m pgcheckpoint
    exit /b
)

if exist "%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python314\pythonw.exe" -m pgcheckpoint
    exit /b
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\pythonw.exe" (
        start "" "%%D\pythonw.exe" -m pgcheckpoint
        exit /b
    )
)

rem Sem pythonw: cai para o modo terminal
goto cli

:cli
title PostgreSQL Checkpoint Manager

where python >nul 2>&1
if %errorlevel%==0 (
    python -m pgcheckpoint %*
    if errorlevel 1 pause
    exit /b
)

if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -m pgcheckpoint %*
    if errorlevel 1 pause
    exit /b
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -m pgcheckpoint %*
        if errorlevel 1 pause
        exit /b
    )
)

echo.
echo [ERRO] Python nao encontrado.
echo Instale o Python em https://www.python.org/downloads/
echo.
pause
