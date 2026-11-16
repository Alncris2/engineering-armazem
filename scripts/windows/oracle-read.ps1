param(
    [Parameter(Mandatory)][ValidateSet('oracle-webagil-dev','oracle-webagil-qas','oracle-webagil-prd','oracle-warehouse-dev','oracle-warehouse-qas','oracle-warehouse-prd')][string]$Connection,
    [string]$SqlFile,
    [string]$ParamsFile,
    [ValidateRange(1, 200)][int]$MaxRows = 100,
    [string]$McpConfig = 'C:\htdocs\squad-ia\.mcp.json',
    [switch]$Probe
)
$ErrorActionPreference = 'Stop'
if (-not $Probe -and -not $SqlFile) { throw 'Informe -SqlFile ou -Probe.' }
if ($Probe -and $SqlFile) { throw 'Escolha -SqlFile ou -Probe.' }
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'services\orchestrator\.venv-workspace\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Python do workspace não encontrado.' }
if (-not (Test-Path -LiteralPath $McpConfig -PathType Leaf)) { throw 'Configuração MCP não encontrada.' }
$config = Get-Content -LiteralPath $McpConfig -Raw | ConvertFrom-Json
$server = $config.mcpServers.$Connection
if (-not $server -or -not $server.env.ORACLE_ENV_FILE) { throw 'Conexão Oracle não configurada no MCP.' }
if (-not (Test-Path -LiteralPath $server.env.ORACLE_ENV_FILE -PathType Leaf)) { throw 'Arquivo de ambiente Oracle não encontrado.' }
$arguments = @((Join-Path $root 'adapters\oracle\read_configured.py'), '--env-file', [string]$server.env.ORACLE_ENV_FILE, '--connect-by', [string]$(if ($server.env.ORACLE_ENV_CONNECT_BY) { $server.env.ORACLE_ENV_CONNECT_BY } else { 'sid' }), '--max-rows', [string]$MaxRows)
if ($server.env.ORACLE_CLIENT_LIB_DIR) { $arguments += @('--client-lib-dir', [string]$server.env.ORACLE_CLIENT_LIB_DIR) }
if ($Probe) { $arguments += '--probe' } else { $arguments += @('--sql-file', (Resolve-Path -LiteralPath $SqlFile).Path) }
if ($ParamsFile) { $arguments += @('--params-file', (Resolve-Path -LiteralPath $ParamsFile).Path) }
& $python @arguments
exit $LASTEXITCODE
