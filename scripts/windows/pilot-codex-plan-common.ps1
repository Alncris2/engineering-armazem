param(
    [Parameter(Mandatory=$true)][ValidateSet('Real','Fake')][string]$Mode,
    [ValidateRange(1,300)][int]$ExecutorTimeoutSeconds = 90
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$tmp = Join-Path $root 'tmp'
$task = Join-Path $root 'config\development\doctor-common-task.txt'
$spec = Join-Path $root 'config\development\doctor-common-spec.md'
$python = Join-Path $root 'services\orchestrator\.venv-workspace\Scripts\python.exe'
$workspace = if ($Mode -eq 'Real') { Join-Path $root 'workspace.py' }
             else { Join-Path $root 'tests\development\fake_workspace_cli.py' }
$thread = 'doctor-common-plan-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$marker = if ($Mode -eq 'Real') { Join-Path $tmp 'codex-langgraph-plan.once' }
          else { Join-Path $tmp ("codex-langgraph-plan.fake.$thread.once") }
$runDir = Join-Path $tmp "development-runs\$thread"
$sandboxDir = Join-Path $tmp "development-sandboxes\$thread"
$claimed = $false

function Emit-Failure([string]$Reason) {
    [ordered]@{status='preflight_failed';reason=$Reason;thread_id=$thread;codex_called=$false} | ConvertTo-Json -Compress
    exit 1
}

if (-not (Test-Path -LiteralPath $tmp -PathType Container)) { Emit-Failure 'tmp_missing' }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { Emit-Failure 'venv_missing' }
if (-not (Test-Path -LiteralPath $task -PathType Leaf) -or -not (Test-Path -LiteralPath $spec -PathType Leaf)) { Emit-Failure 'doctor_input_missing' }
if ($Mode -eq 'Real') {
    if ((Test-Path Env:CODEX_PERMISSION_PROFILE) -or (Test-Path Env:CODEX_SANDBOX_NETWORK_DISABLED)) {
        Emit-Failure 'managed_context_detected'
    }
    if (-not $env:LOCALAPPDATA) { Emit-Failure 'localappdata_missing' }
    $wrapper = Join-Path $env:LOCALAPPDATA 'Author Software\nvm\installs\v26.13.1\codex.cmd'
    if (-not (Test-Path -LiteralPath $wrapper -PathType Leaf)) { Emit-Failure 'pinned_wrapper_missing' }
}
if (Test-Path -LiteralPath $marker) { Emit-Failure 'one_shot_already_claimed' }
if ((Test-Path -LiteralPath $runDir) -or (Test-Path -LiteralPath $sandboxDir)) { Emit-Failure 'thread_path_collision' }
$specBody = Get-Content -LiteralPath $spec -Raw -Encoding UTF8
$openQuestions = [regex]::Match($specBody, '(?ms)^## Open Questions[ \t]*\r?\n(?<body>.*?)(?=^#{1,2}[ \t]+|\z)')
if (-not $openQuestions.Success -or $openQuestions.Groups['body'].Value.Trim() -ne 'Nenhuma.') { Emit-Failure 'doctor_spec_open_questions' }
$existingCodexProcesses = @(Get-Process -Name codex -ErrorAction SilentlyContinue).Count

try {
    $stream = [System.IO.File]::Open($marker, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($thread)
        $stream.Write($bytes, 0, $bytes.Length)
    } finally { $stream.Dispose() }
    $claimed = $true
} catch [System.IO.IOException] { Emit-Failure 'one_shot_already_claimed' }

function Invoke-RootCli([string[]]$Argv) {
    $raw = & $python $workspace @Argv 2>$null
    $code = $LASTEXITCODE
    $line = @($raw | Where-Object { $_ -is [string] -and $_.TrimStart().StartsWith('{') }) | Select-Object -Last 1
    $payload = $null
    if ($line) { try { $payload = $line | ConvertFrom-Json } catch {} }
    return [pscustomobject]@{exit_code=$code;payload=$payload}
}

$original = (Get-Location).Path
try {
    Set-Location -LiteralPath $root
    $start = Invoke-RootCli -Argv @('--json','development','start','--thread',$thread,'--issue','LOCAL-DOCTOR-PLAN',
                                    '--executor','codex','--task-file',$task,'--executor-timeout',"$ExecutorTimeoutSeconds")
    # A second Python process reads the durable PostgreSQL checkpoint; status never runs Codex.
    $status = Invoke-RootCli -Argv @('--json','development','status','--thread',$thread)
    $state = if ($status.payload -and $status.payload.data) { $status.payload.data }
             elseif ($start.payload -and $start.payload.data) { $start.payload.data }
             else { $null }
    $reopened = [bool]($status.payload -and $status.payload.data -and $status.payload.data.thread_id -eq $thread)
    $gate = if ($state -and $state.gates) { $state.gates.plan } else { $null }
    $diagnostic = $null
    $diagnosticPath = Join-Path $runDir 'diagnostic.json'
    if (Test-Path -LiteralPath $diagnosticPath -PathType Leaf) {
        try {
            $d = Get-Content -LiteralPath $diagnosticPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $diagnostic = [ordered]@{category=$d.category;exit_code=$d.exit_code;stdout_bytes=$d.stdout_bytes;
                stderr_bytes=$d.stderr_bytes;stdout_sha256=$d.stdout_sha256;stderr_sha256=$d.stderr_sha256;
                event_counts=$d.event_counts}
        } catch { $diagnostic = [ordered]@{category='unreadable'} }
    }
    $artifactPresent = Test-Path -LiteralPath (Join-Path $runDir 'plan-1.txt') -PathType Leaf
    $outcome = if ($reopened -and $state.status -eq 'held' -and $gate.passed -eq $true -and
                   ($Mode -eq 'Fake' -or $artifactPresent)) { 'held_plan_passed' }
               elseif ($reopened -and $gate.passed -eq $false) { 'held_gate_failed' }
               else { 'inconclusive' }
    [ordered]@{status=$outcome;mode=$Mode;checkpoint_kind=$(if($Mode -eq 'Real'){'postgres'}else{'fake_file'});
        thread_id=$thread;executor='codex';start_exit_code=$start.exit_code;
        status_exit_code=$status.exit_code;checkpoint_reopened=$reopened;plan_gate_passed=$gate.passed;
        plan_attempts=$state.attempts.plan;codex_processes_before=$existingCodexProcesses;
        one_shot_claimed=$claimed;plan_artifact_present=$artifactPresent;
        diagnostic=$diagnostic} | ConvertTo-Json -Depth 8 -Compress
    if ($outcome -eq 'held_plan_passed') { exit 0 }
    exit 1
} catch {
    [ordered]@{status='script_error';thread_id=$thread;one_shot_claimed=$claimed;
        checkpoint_reopened=$false} | ConvertTo-Json -Compress
    exit 1
} finally {
    Set-Location -LiteralPath $original
}
