@echo off
REM Arranca NEXUS SYSTEM AI en esta ventana (Ctrl+C para detener).
cd /d "%~dp0"

REM Usa el Python portable de .\runtime si existe; si no, el del sistema.
if exist "runtime\python.exe" (
    set "PY=runtime\python.exe"
) else (
    set "PY=python"
)

"%PY%" run.py
echo.
pause
