@echo off
REM NEXUS SYSTEM AI - gestor del servicio en segundo plano.
REM Uso: service.bat [install^|start^|stop^|status^|uninstall]
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service.ps1" install
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service.ps1" %*
)
endlocal
