param(
    [Parameter(Mandatory=$true)][ValidateSet('Real','Fake')][string]$Mode,
    [ValidateSet('Success','Permission')][string]$FakeOutcome = 'Success',
    [ValidateRange(1,30)][int]$TimeoutSeconds = 12
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $root 'services\orchestrator\.venv-workspace\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    @{status='preflight_failed';reason='venv_missing'} | ConvertTo-Json -Compress
    exit 1
}
$moduleRoot = Join-Path $root 'services\orchestrator'
$bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from development.context_probe import main;sys.exit(main())'
$original = (Get-Location).Path
try {
    Set-Location -LiteralPath $root
    $raw = & $python -c $bootstrap $moduleRoot --root $root --mode $Mode.ToLowerInvariant() --fake-outcome $FakeOutcome.ToLowerInvariant() --timeout $TimeoutSeconds 2>$null
    $childExit = $LASTEXITCODE
    $data = $raw | Select-Object -Last 1 | ConvertFrom-Json
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    $data.context | Add-Member -NotePropertyName powershell_edition -NotePropertyValue $PSVersionTable.PSEdition -Force
    $data.context | Add-Member -NotePropertyName powershell_major -NotePropertyValue $PSVersionTable.PSVersion.Major -Force
    $data.context | Add-Member -NotePropertyName account_matches_tmp_owner -NotePropertyValue ($identity.Name -eq (Get-Acl -LiteralPath (Join-Path $root 'tmp')).Owner) -Force
    $data.context | Add-Member -NotePropertyName elevated -NotePropertyValue ($principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) -Force
    $data | ConvertTo-Json -Depth 8 -Compress
    if ($childExit -eq 0 -and $data.status -eq 'passed') { exit 0 }
    exit 1
} catch {
    @{status='failed';reason='powershell_wrapper_error'} | ConvertTo-Json -Compress
    exit 1
} finally {
    Set-Location -LiteralPath $original
}
