param([string]$EnvFile = ".env.production")

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repo $EnvFile
if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Arquivo de ambiente não encontrado: $envPath"
}

$ambienteAnterior = $env:SISMOD_ENV_FILE
Push-Location $repo
try {
    $env:SISMOD_ENV_FILE = $envPath
    docker compose --env-file $envPath -f (Join-Path $PSScriptRoot "compose.producao.yaml") config --quiet
    if ($LASTEXITCODE -ne 0) { throw "A configuração Docker de produção é inválida." }
    & ".\venv\Scripts\python.exe" manage.py check
    if ($LASTEXITCODE -ne 0) { throw "O Django encontrou erro de configuração." }
    & ".\venv\Scripts\python.exe" manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE -ne 0) { throw "Existem alterações de modelo sem migration." }
} finally {
    if ($null -eq $ambienteAnterior) { Remove-Item Env:SISMOD_ENV_FILE -ErrorAction SilentlyContinue }
    else { $env:SISMOD_ENV_FILE = $ambienteAnterior }
    Pop-Location
}

Write-Host "Configuração validada. Nenhum serviço foi iniciado e nenhum comando DJI foi enviado."
