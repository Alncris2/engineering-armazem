param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z][A-Za-z0-9_]*-[0-9]+$')][string]$Key,
    [Parameter(Mandatory)][string]$Repository,
    [ValidatePattern('^[A-Za-z0-9._-]+$')][string]$BaseBranch = 'dev',
    [ValidatePattern('^[A-Za-z0-9._-]+$')][string]$WorktreeName = 'webagil-back',
    [string]$DemandasRoot = 'C:\htdocs\Demandas',
    [string]$ProfilePath = $PROFILE.CurrentUserCurrentHost,
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
$Key = $Key.ToUpperInvariant()
$Repository = (Resolve-Path -LiteralPath $Repository).Path
if (-not (Test-Path -LiteralPath (Join-Path $Repository '.git'))) { throw 'Repository must be a Git checkout.' }
if (-not (Test-Path -LiteralPath $DemandasRoot -PathType Container)) { throw 'Demandas root does not exist.' }
if (-not (Test-Path -LiteralPath $ProfilePath -PathType Leaf)) { throw 'PowerShell profile with baixar-jira not found.' }
$branch = $Key
$folder = Join-Path $DemandasRoot $Key
$worktree = Join-Path $folder $WorktreeName
if ($WorktreeName -in @('.', '..')) { throw 'Invalid worktree directory name.' }
if (-not [IO.Path]::GetFullPath($folder).StartsWith(([IO.Path]::GetFullPath($DemandasRoot).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Demand folder escapes root.' }
if (-not [IO.Path]::GetFullPath($worktree).StartsWith(([IO.Path]::GetFullPath($folder).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Worktree escapes demand folder.' }
& git -C $Repository check-ref-format --branch $branch *> $null
if ($LASTEXITCODE -ne 0) { throw 'Invalid branch name.' }
& git -C $Repository rev-parse --verify "refs/remotes/origin/$BaseBranch^{commit}" *> $null
if ($LASTEXITCODE -ne 0) { throw 'Base branch origin/<name> is not available locally.' }
$existing = & git -C $Repository branch --list $branch
if ($existing) { throw 'Branch already exists locally; inspect its worktree and upstream before retrying.' }
if (Test-Path -LiteralPath $worktree) { throw 'Worktree destination already exists.' }
if ($Plan) {
    [pscustomobject]@{ key=$Key; folder=$folder; worktree=$worktree; branch=$branch; base="origin/$BaseBranch"; upstream="origin/$branch"; evidence='baixar-jira'; publish='git push -u origin' } | ConvertTo-Json -Compress
    exit 0
}
New-Item -ItemType Directory -Path $folder -Force | Out-Null
. $ProfilePath
if (-not (Get-Command baixar-jira -CommandType Function -ErrorAction SilentlyContinue)) { throw 'baixar-jira is not defined in the profile.' }
baixar-jira $Key
& git -C $Repository worktree add --no-track -b $branch $worktree "origin/$BaseBranch"
if ($LASTEXITCODE -ne 0) { throw 'Could not create demand worktree.' }
& git -C $worktree push -u origin "HEAD:refs/heads/$branch"
if ($LASTEXITCODE -ne 0) { throw 'Worktree created but remote branch/upstream is pending; inspect before retrying.' }
$upstream = (& git -C $worktree rev-parse --abbrev-ref --symbolic-full-name '@{upstream}').Trim()
if ($LASTEXITCODE -ne 0 -or $upstream -ne "origin/$branch") { throw 'Demand branch upstream does not match its remote branch.' }
$head = (& git -C $worktree rev-parse HEAD).Trim()
[pscustomobject]@{ key=$Key; folder=$folder; worktree=$worktree; branch=$branch; base="origin/$BaseBranch"; upstream=$upstream; head=$head; evidence='downloaded' } | ConvertTo-Json -Compress
