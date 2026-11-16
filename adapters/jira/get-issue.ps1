param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Z][A-Z0-9_]+-[0-9]+$')][string]$Key,
    [ValidateRange(1, 120)][int]$TimeoutSec = 20
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'services\orchestrator\.venv-workspace\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Python do workspace não encontrado.' }
$credentialPath = Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'JiraDownloader\credential.xml'
if (-not (Test-Path -LiteralPath $credentialPath -PathType Leaf)) { throw 'Existing Jira credential was not found.' }
$credential = Import-Clixml -LiteralPath $credentialPath
if ($credential -isnot [System.Management.Automation.PSCredential]) { throw 'Existing Jira credential has an invalid format.' }
$pair = '{0}:{1}' -f $credential.UserName, $credential.GetNetworkCredential().Password
$authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair))
$pair = $null
$credential = $null
try {
    $authorization | & $python (Join-Path $PSScriptRoot 'get_issue_direct.py') --key $Key --timeout $TimeoutSec
    if ($LASTEXITCODE -ne 0) { throw 'Jira GET failed.' }
} finally {
    $authorization = $null
}
