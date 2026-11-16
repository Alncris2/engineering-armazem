param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$venvPython = Join-Path $root 'services\orchestrator\.venv-workspace\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) { throw 'Install the Workspace Python environment before using the CLI.' }
& $venvPython (Join-Path $root 'workspace.py') @Arguments
exit $LASTEXITCODE
