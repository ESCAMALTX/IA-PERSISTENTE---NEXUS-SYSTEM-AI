@echo off
REM ============================================================
REM  NEXUS SYSTEM AI - INSTALADOR
REM  Prepara todo lo necesario en esta misma carpeta.
REM  NO requiere tener Python instalado en el equipo.
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PYVER=3.12.8"
set "PYDIR=%~dp0runtime"
set "PYEXE=%PYDIR%\python.exe"
set "ZIPURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip"
set "PIPURL=https://bootstrap.pypa.io/get-pip.py"
set "TMPZIP=%TEMP%\nexus-python-%PYVER%.zip"
set "TMPPIP=%TEMP%\nexus-get-pip.py"

echo.
echo  ============================================================
echo    NEXUS SYSTEM AI - Instalacion
echo  ============================================================
echo.

REM -------------------- 1. Python portable --------------------
if exist "%PYEXE%" (
    echo  [1/5] Python portable ya presente. Omitido.
    goto :pth
)

echo  [1/5] Descargando Python portable %PYVER% ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%ZIPURL%' -OutFile '%TMPZIP%' -UseBasicParsing -TimeoutSec 300; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo.
    echo  ERROR: no se pudo descargar Python.
    echo  Comprueba tu conexion a internet y vuelve a ejecutar este archivo.
    echo.
    pause
    exit /b 1
)
echo  [1/5] Extrayendo ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath '%TMPZIP%' -DestinationPath '%PYDIR%' -Force"
if errorlevel 1 (
    echo.
    echo  ERROR: no se pudo extraer Python.
    pause
    exit /b 1
)
del /q "%TMPZIP%" >nul 2>&1
echo  [1/5] Python listo.

REM ------------- 2. Habilitar site-packages en el ._pth -------------
:pth
set "PTHFILE="
for %%f in ("%PYDIR%\python*._pth") do set "PTHFILE=%%f"
if not defined PTHFILE (
    echo  [2/5] Aviso: no se encontro el archivo ._pth.
    goto :pip
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\preparar_python_portable.ps1" -PythonDir "%PYDIR%"
if errorlevel 1 (
    echo.
    echo  ERROR: no se pudo preparar el Python portable.
    pause
    exit /b 1
)
echo  [2/5] Python portable configurado.

REM ------------------------ 3. pip ------------------------
:pip
"%PYEXE%" -m pip --version >nul 2>&1
if not errorlevel 1 (
    echo  [3/5] pip ya instalado. Omitido.
    goto :libs
)
echo  [3/5] Instalando pip ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%PIPURL%' -OutFile '%TMPPIP%' -UseBasicParsing -TimeoutSec 120; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo.
    echo  ERROR: no se pudo descargar pip.
    pause
    exit /b 1
)
"%PYEXE%" "%TMPPIP%" --no-warn-script-location --disable-pip-version-check -q
del /q "%TMPPIP%" >nul 2>&1
"%PYEXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: pip no quedo operativo.
    echo  Borra la carpeta "runtime" y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)
echo  [3/5] pip listo.

REM --------------------- 4. Librerias ---------------------
:libs
echo  [4/5] Instalando librerias (puede tardar un par de minutos) ...
"%PYEXE%" -m pip install --no-warn-script-location --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ERROR: fallo la instalacion de las librerias.
    echo  Revisa tu conexion a internet y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)
"%PYEXE%" -c "import fastapi, uvicorn, psutil, httpx" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: las librerias no cargan correctamente.
    pause
    exit /b 1
)
echo  [4/5] Librerias OK.

REM ------------------- 5. Clave de API -------------------
if exist ".env" (
    echo  [5/5] El archivo .env ya existe. Omitido.
    goto :fin
)
echo  [5/5] Configurando la clave de DeepSeek.
echo.
echo        Puedes pedir una en: https://platform.deepseek.com/api_keys
echo        Si la dejas vacia el programa funciona, pero sin IA.
echo.
set "KEY="
set /p "KEY=        Pega tu clave sk-... y pulsa Enter: "
if "!KEY!"=="" (
    copy /y ".env.example" ".env" >nul 2>&1
    echo.
    echo        Sin clave. Se creo .env vacio: puedes editarlo luego.
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$lines = @('# Configuracion de NEXUS SYSTEM AI', 'DEEPSEEK_API_KEY=!KEY!', 'DEEPSEEK_BASE_URL=https://api.deepseek.com', 'DEEPSEEK_MODEL=deepseek-chat', '', 'NEXUS_HOST=127.0.0.1', 'NEXUS_PORT=8000', '', 'CPU_ALERT_THRESHOLD=85', 'RAM_ALERT_THRESHOLD=85', 'DISK_ALERT_THRESHOLD=90', 'MONITOR_INTERVAL=5', 'ALERT_COOLDOWN=120'); Set-Content -LiteralPath '.env' -Value $lines -Encoding UTF8"
    echo.
    echo        Clave guardada en .env
)

:fin
echo.
echo  ============================================================
echo    LISTO. Ahora puedes usar:
echo.
echo      start.bat       abrir el panel (uso normal)
echo      service.bat     que arranque solo con Windows
echo.
echo    Panel: http://127.0.0.1:8000
echo  ============================================================
echo.
pause
endlocal
