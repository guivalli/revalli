# Instalação rápida do ReValli no Windows (precisa do Docker Desktop ligado).
#
#   .\install.ps1                 gera o .env com senhas novas e sobe tudo
#   .\install.ps1 -Port 9000      usa outra porta (padrão 8080)
#   .\install.ps1 -NoStart        só gera o .env
#
# Não mexe em um .env que já existe: para trocar a configuração, edite o arquivo.
param(
    [int]$Port = 8080,
    [switch]$NoStart
)
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function New-Secret {
    $bytes = New-Object 'System.Byte[]' 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

if (Test-Path .env) {
    Write-Host 'Mantendo o .env que já existe.'
} else {
    if (-not (Test-Path .env.example)) {
        throw 'Falta o arquivo .env.example ao lado deste script.'
    }
    $password = New-Secret
    $lines = Get-Content .env.example | ForEach-Object {
        if ($_ -match '^POSTGRES_PASSWORD=') { "POSTGRES_PASSWORD=$password" }
        elseif ($_ -match '^HTTP_PORT=') { "HTTP_PORT=$Port" }
        elseif ($_ -match '^PUBLIC_URL=') { "PUBLIC_URL=http://localhost:$Port" }
        else { $_ }
    }
    # UTF-8 sem BOM, que é o que o Compose espera
    [System.IO.File]::WriteAllLines((Join-Path $PSScriptRoot '.env'), $lines, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host 'Criei o .env com uma senha de banco gerada para esta instalação.'
}

$portInUse = ((Get-Content .env | Where-Object { $_ -match '^HTTP_PORT=' } | Select-Object -First 1) -replace '^HTTP_PORT=', '')
if (-not $portInUse) { $portInUse = '8080' }

if ($NoStart) {
    Write-Host 'Pronto. Suba com: docker compose up -d'
    exit 0
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Não achei o Docker. Instale o Docker Desktop, abra-o e rode este script de novo.'
}

Write-Host 'Subindo o ReValli (a primeira vez baixa ou constrói as imagens)...'
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw 'O Docker Compose falhou. Veja a mensagem acima.' }

$url = "http://localhost:$portInUse"
Write-Host -NoNewline 'Esperando a API responder'
for ($i = 0; $i -lt 60; $i++) {
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "$url/api/health" -TimeoutSec 3 | Out-Null
        Write-Host ''
        Write-Host "Pronto: abra $url"
        Write-Host 'No primeiro acesso, crie a conta de administrador na própria tela.'
        Start-Process $url
        exit 0
    } catch {
        Write-Host -NoNewline '.'
        Start-Sleep -Seconds 3
    }
}
Write-Host ''
throw 'A API ainda não respondeu. Veja os registros com: docker compose logs api'
