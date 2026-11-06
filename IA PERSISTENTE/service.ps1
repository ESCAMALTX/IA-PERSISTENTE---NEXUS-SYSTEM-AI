# NEXUS SYSTEM AI - arranque en segundo plano (sin permisos de administrador)
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\service.ps1 install
#   powershell -ExecutionPolicy Bypass -File .\service.ps1 status
#   ... start | stop | uninstall
#
# Instala un acceso en la carpeta Inicio del usuario que lanza run.py de forma
# oculta (sin ventana de consola) cada vez que se inicia sesión. No usa el
# Programador de tareas, por lo que no requiere privilegios de administrador.

param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "start", "stop", "status", "uninstall")]
    [string]$Command = "install"
)

$ErrorActionPreference = "Stop"

$AppName    = "NexusSystemAI"
$ProjectDir = $PSScriptRoot
$PythonExe  = (Get-Command python -ErrorAction Stop).Source
$Pythonw    = Join-Path (Split-Path $PythonExe) "pythonw.exe"
if (-not (Test-Path $Pythonw)) { $Pythonw = $PythonExe }
$RunScript  = Join-Path $ProjectDir "run.py"

$StartupDir = [Environment]::GetFolderPath("Startup")
$Launcher   = Join-Path $StartupDir "$AppName.vbs"
$Url        = "http://127.0.0.1:8000"

function Get-NexusProcess {
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and
            ($_.CommandLine -like "*$RunScript*" -or
             ($_.CommandLine -like "*run.py*" -and $_.ExecutablePath -and
              (Split-Path $_.ExecutablePath) -eq (Split-Path $PythonExe)))
        }
}

function New-LauncherContent {
    $workDir = $ProjectDir.Replace('"', '""')
    $exe     = $Pythonw.Replace('"', '""')
    $script  = $RunScript.Replace('"', '""')
    # La ruta absoluta evita depender del directorio de trabajo al detectar el proceso.
    return @"
' Lanzador generado por NEXUS SYSTEM AI - no editar a mano
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "$workDir"
shell.Run """$exe"" ""$script""", 0, False
"@
}

function Start-Nexus {
    $existing = Get-NexusProcess
    if ($existing) {
        Write-Host "Ya esta en ejecucion (PID $($existing.ProcessId -join ', '))."
        return
    }
    $tmp = Join-Path $env:TEMP "$AppName-run.vbs"
    Set-Content -Path $tmp -Value (New-LauncherContent) -Encoding ASCII
    Start-Process -FilePath "wscript.exe" -ArgumentList "`"$tmp`"" -WindowStyle Hidden

    # Esperamos a que el panel responda (uvicorn tarda unos segundos).
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 700
        try {
            $resp = Invoke-RestMethod -Uri "$Url/api/health" -TimeoutSec 2 -ErrorAction Stop
            if ($resp.status -eq "ok") { $ready = $true; break }
        } catch { }
    }

    $proc = Get-NexusProcess
    if ($ready -and $proc) {
        Write-Host "NEXUS iniciado (PID $($proc.ProcessId -join ', ')). Panel: $Url"
    } elseif ($proc) {
        Write-Host "NEXUS en marcha (PID $($proc.ProcessId -join ', ')), pero el panel aun no responde. Revisa data\nexus-stdout.log" -ForegroundColor Yellow
    } else {
        Write-Host "No se pudo arrancar. Revisa data\nexus-stdout.log" -ForegroundColor Yellow
    }
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}

function Stop-Nexus {
    $procs = Get-NexusProcess
    if (-not $procs) { Write-Host "No esta en ejecucion."; return }
    foreach ($p in $procs) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Detenido PID $($p.ProcessId)."
    }
}

switch ($Command) {

    "install" {
        Set-Content -Path $Launcher -Value (New-LauncherContent) -Encoding ASCII
        Write-Host "Instalado en el arranque de Windows: $Launcher"
        Start-Nexus
    }

    "start"  { Start-Nexus }

    "stop"   { Stop-Nexus }

    "status" {
        $procs = Get-NexusProcess
        if ($procs) {
            $procs | Select-Object ProcessId, Name, CreationDate | Format-Table -AutoSize
            Write-Host "Panel: $Url"
        } else {
            Write-Host "No esta en ejecucion."
        }
        Write-Host ("En el arranque: " + $(if (Test-Path $Launcher) { "si" } else { "no" }))
    }

    "uninstall" {
        Stop-Nexus
        if (Test-Path $Launcher) {
            Remove-Item $Launcher -Force
            Write-Host "Eliminado del arranque de Windows."
        } else {
            Write-Host "No estaba instalado en el arranque."
        }
    }
}
