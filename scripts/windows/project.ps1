param(
    [Parameter(Mandatory=$true)][string]$Slug,
    [string]$ApiUrl = 'http://127.0.0.1:8088'
)
$ErrorActionPreference = 'Stop'
if ($ApiUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') { throw 'The API must use loopback HTTP.' }
if ($Slug -notmatch '^[a-z0-9-]+$') { throw 'Invalid project slug.' }
$projects = (Invoke-RestMethod -Method Get -Uri "$ApiUrl/api/projects").data
$selected = @($projects | Where-Object slug -eq $Slug)
if ($selected.Count -ne 1) { throw 'Project not found or ambiguous.' }
$detail = Invoke-RestMethod -Method Get -Uri "$ApiUrl/api/projects/$($selected[0].id)"
$detail | ConvertTo-Json -Depth 20
