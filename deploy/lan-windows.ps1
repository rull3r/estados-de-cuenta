#Requires -RunAsAdministrator
<#
    estados-de-cuenta · preparar acceso LAN en Windows

    - Abre el puerto 8000 solo para redes privadas (idempotente).
    - Muestra las URLs para entrar desde cualquier equipo de la red.
    - Verifica que Docker esté corriendo y levanta el servicio.

    Uso (PowerShell como Administrador, desde la raíz del repo):
        powershell -ExecutionPolicy Bypass -File deploy/lan-windows.ps1
#>

$ErrorActionPreference = "Stop"
$Port = 8000
$RuleName = "estados-de-cuenta ($Port)"

Write-Host ""
Write-Host "== estados-de-cuenta: preparar acceso en tu red ==" -ForegroundColor Yellow

# 1. Regla de firewall (no duplica si ya existe)
$existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if (-not $existing) {
    New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -Protocol TCP `
        -LocalPort $Port -Action Allow -Profile Private | Out-Null
    Write-Host "[ok] Regla de firewall creada: TCP $Port para redes privadas."
} else {
    Write-Host "[ok] La regla de firewall ya existia."
}

# 2. Direcciones para entrar desde la red
$ips = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -ExpandProperty IPAddress

Write-Host ""
Write-Host "Entra desde cualquier dispositivo de tu red en:" -ForegroundColor Cyan
Write-Host "   http://localhost:$Port   (en esta misma maquina)"
foreach ($ip in $ips) {
    Write-Host "   http://${ip}:$Port"
}
Write-Host ""
Write-Host "Tip: reserva esa IP en tu router (DHCP estatico) para que no cambie." -ForegroundColor DarkGray

# 3. Docker disponible
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Docker no esta corriendo. Abre Docker Desktop y vuelve a ejecutar este script." -ForegroundColor Red
    exit 1
}

# 4. Levantar el servicio
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    docker compose up -d
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "[ok] Servicio levantado." -ForegroundColor Green
Write-Host "     La politica 'restart: unless-stopped' lo mantiene arriba y lo reinicia" -ForegroundColor DarkGray
Write-Host "     cuando Docker arranque con la maquina." -ForegroundColor DarkGray
Write-Host ""
