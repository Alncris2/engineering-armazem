param(
    [Parameter(Mandatory)][string]$Query,
    [Parameter(Mandatory)][string]$Start,
    [Parameter(Mandatory)][string]$End,
    [string]$SquadEnv = 'C:\htdocs\squad-ia\.env',
    [ValidateRange(1, 120)][int]$TimeoutSec = 20
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $SquadEnv -PathType Leaf)) { throw 'Squad .env not found.' }
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'services\orchestrator\.venv-workspace\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Python do workspace não encontrado.' }
$keys = @('GRAFANA_URL','GRAFANA_USERNAME','GRAFANA_PASSWORD','GRAFANA_TOKEN','GRAFANA_DATASOURCE_UID')
$saved = @{}
foreach ($key in $keys) { $saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
try {
    foreach ($line in [IO.File]::ReadAllLines($SquadEnv)) {
        if ($line -match '^\s*(GRAFANA_URL|GRAFANA_USERNAME|GRAFANA_PASSWORD|GRAFANA_TOKEN|GRAFANA_DATASOURCE_UID)=(.*)$') {
            $value = $Matches[2].Trim()
            if ($value.Length -ge 2 -and $value[0] -eq $value[-1] -and ($value[0] -eq '"' -or $value[0] -eq "'")) { $value = $value.Substring(1, $value.Length - 2) }
            [Environment]::SetEnvironmentVariable($Matches[1], $value, 'Process')
        }
    }
    & $python (Join-Path $root 'adapters\grafana\query.py') --query $Query --start $Start --end $End --timeout $TimeoutSec
    $code = $LASTEXITCODE
} finally {
    foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key, $saved[$key], 'Process') }
}
exit $code
