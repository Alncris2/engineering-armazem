param(
    [Parameter(Mandatory=$true)][ValidateSet('codex', 'claude')][string]$Executor,
    [Parameter(Mandatory=$true)][string]$RunId,
    [string]$CaptureFile,
    [switch]$ClaudeFreshOrExplicitResume,
    [string]$ApiUrl = 'http://127.0.0.1:8088'
)

$ErrorActionPreference = 'Stop'
if ($ApiUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') { throw 'The API must use loopback HTTP.' }
if ($RunId -notmatch '^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$') { throw 'RunId must be a UUID.' }

$sessionId = $null
$method = $null
if ($CaptureFile) {
    $path = (Resolve-Path -LiteralPath $CaptureFile).Path
    if ($Executor -eq 'claude') {
        $result = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        if ($result.type -ne 'result' -or $result.subtype -ne 'success' -or $result.is_error -ne $false) {
            throw 'Claude result is not a successful session.'
        }
        $sessionId = $result.session_id
        $method = 'claude:print-json'
    } else {
        $started = $null
        $completed = $false
        foreach ($line in Get-Content -LiteralPath $path) {
            if (-not $line.Trim()) { continue }
            $event = $line | ConvertFrom-Json
            if ($event.type -eq 'thread.started') { $started = $event.thread_id }
            if ($event.type -eq 'turn.completed') { $completed = $true }
            if ($event.type -in @('turn.failed', 'error')) { throw 'Codex trace contains a failure.' }
        }
        if (-not $started -or -not $completed) { throw 'Codex trace lacks thread.started or turn.completed.' }
        $sessionId = $started
        $method = 'codex:exec-json'
    }
} elseif ($Executor -eq 'claude') {
    if (-not $ClaudeFreshOrExplicitResume) { throw 'Claude environment capture requires a fresh session or --resume with an explicit ID; pass -ClaudeFreshOrExplicitResume only in that case.' }
    $sessionId = $env:CLAUDE_CODE_SESSION_ID
    $method = 'claude:env'
    if (-not $sessionId) { throw 'CLAUDE_CODE_SESSION_ID is absent. Run this inside a Claude Code tool subprocess.' }
} else {
    $sessionId = $env:CODEX_THREAD_ID
    $method = 'codex:env+session-meta'
    if (-not $sessionId) { throw 'CODEX_THREAD_ID is absent. Run this inside the Codex session.' }
    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
    $sessionRoot = Join-Path $codexHome 'sessions'
    $file = Get-ChildItem -LiteralPath $sessionRoot -Recurse -Filter "*$sessionId*.jsonl" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $file) { throw 'The Codex session file was not found.' }
    $first = Get-Content -LiteralPath $file.FullName -TotalCount 1 | ConvertFrom-Json
    if ($first.type -ne 'session_meta' -or $first.payload.id -ne $sessionId) { throw 'Codex session metadata does not match CODEX_THREAD_ID.' }
}

if ($sessionId -notmatch '^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$') { throw 'Captured session ID is not a UUID.' }
$null = Invoke-RestMethod -Method Get -Uri "$ApiUrl/api/runs/$RunId"
$body = @{executor=$Executor; external_session_id=$sessionId; capture_method=$method} | ConvertTo-Json -Compress
$stored = (Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/runs/$RunId/sessions" -ContentType 'application/json' -Body $body).data
if ($stored.external_session_id -ne $sessionId -or $stored.run_id -ne $RunId) { throw 'Stored session does not match the captured session.' }
[pscustomobject]@{run_id=$RunId; executor=$Executor; session_id=$sessionId; capture_method=$method; record_id=$stored.id} | ConvertTo-Json -Compress
