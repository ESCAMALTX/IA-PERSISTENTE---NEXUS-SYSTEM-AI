# Habilita "import site" en el ._pth del Python portable.
# El Python "embed" de Windows ignora las librerias instaladas con pip hasta que
# se descomenta esa linea. Lo hace de forma idempotente.
#
# Uso: powershell -ExecutionPolicy Bypass -File tools\preparar_python_portable.ps1 -PythonDir "C:\ruta\runtime"

param(
    [Parameter(Mandatory = $true)]
    [string]$PythonDir
)

$ErrorActionPreference = "Stop"

$pth = Get-ChildItem -Path $PythonDir -Filter "python*._pth" -ErrorAction SilentlyContinue |
       Select-Object -First 1

if (-not $pth) {
    Write-Host "No se encontro pythonX.Y._pth en $PythonDir"
    exit 2
}

$lines = @(Get-Content -LiteralPath $pth.FullName)
$yaActivo = $lines | Where-Object { $_ -match '^\s*import\s+site\s*$' }
if ($yaActivo) {
    Write-Host "Ya estaba configurado: $($pth.Name)"
    exit 0
}

$cambiado = $false
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*#\s*import\s+site\s*$') {
        $lines[$i] = 'import site'
        $cambiado = $true
    }
}
if (-not $cambiado) { $lines += 'import site' }

Set-Content -LiteralPath $pth.FullName -Value $lines -Encoding ASCII

if ((Get-Content -LiteralPath $pth.FullName) -match '^\s*import\s+site\s*$') {
    Write-Host "Configurado: $($pth.Name)"
    exit 0
}

Write-Host "No se pudo configurar $($pth.Name)"
exit 1
