param(
    [string]$McpConfig = 'C:\htdocs\squad-ia\.mcp.json',
    [string]$SquadEnv = 'C:\htdocs\squad-ia\.env',
    [string]$TerminalSettings = (Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json'),
    [string]$ProfilePath = $PROFILE.CurrentUserCurrentHost
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$result = [ordered]@{
    mcp_config = Test-Path -LiteralPath $McpConfig -PathType Leaf
    squad_env = Test-Path -LiteralPath $SquadEnv -PathType Leaf
    terminal_settings = Test-Path -LiteralPath $TerminalSettings -PathType Leaf
    powershell_profile = Test-Path -LiteralPath $ProfilePath -PathType Leaf
    jira_credential = Test-Path -LiteralPath (Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'JiraDownloader\credential.xml') -PathType Leaf
    workspace_python = Test-Path -LiteralPath (Join-Path $root 'services\orchestrator\.venv-workspace\Scripts\python.exe') -PathType Leaf
    oracle_connections = @()
}
if ($result.mcp_config) {
    $config = Get-Content -LiteralPath $McpConfig -Raw | ConvertFrom-Json
    $result.oracle_connections = @($config.mcpServers.PSObject.Properties | Where-Object Name -like 'oracle-*' | ForEach-Object {
        [pscustomobject]@{ name=$_.Name; env_file_present=(Test-Path -LiteralPath $_.Value.env.ORACLE_ENV_FILE -PathType Leaf); client_present=(Test-Path -LiteralPath $_.Value.env.ORACLE_CLIENT_LIB_DIR -PathType Container) }
    })
}
$result | ConvertTo-Json -Depth 5
