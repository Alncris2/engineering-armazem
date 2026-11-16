param(
    [ValidateSet('list','open')][string]$Action = 'list',
    [ValidateSet('qas-back','prd-back-novo','prd-back-antigo')][string]$Server,
    [string]$Settings = (Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json')
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Settings -PathType Leaf)) { throw 'Windows Terminal settings not found.' }
$names = [ordered]@{
    'qas-back' = 'WebÁgil QAS Back'
    'prd-back-novo' = 'WebÁgil PRD Back (novo)'
    'prd-back-antigo' = 'WebÁgil PRD Back (Antigo)'
}
$config = Get-Content -LiteralPath $Settings -Raw | ConvertFrom-Json
$profiles = foreach ($alias in $names.Keys) {
    $found = @($config.profiles.list | Where-Object { $_.name -ceq $names[$alias] })
    if ($found.Count -ne 1 -or -not $found[0].guid -or $found[0].commandline -notmatch '(?i)\bssh\b') { throw "SSH profile missing or invalid: $alias" }
    [pscustomobject]@{ alias=$alias; name=$found[0].name; guid=$found[0].guid }
}
if ($Action -eq 'list') { $profiles | ConvertTo-Json -Depth 3; exit 0 }
if (-not $Server) { throw 'Informe -Server para abrir uma sessão.' }
$selected = $profiles | Where-Object alias -eq $Server
& wt -p $selected.guid
exit $LASTEXITCODE
