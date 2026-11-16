param(
    [string]$TicketId,
    [string]$TicketKey,
    [string]$ApiUrl = 'http://127.0.0.1:8088'
)
$ErrorActionPreference = 'Stop'
if ($ApiUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') { throw 'ApiUrl must use loopback HTTP.' }
if (([bool]$TicketId) -eq ([bool]$TicketKey)) { throw 'Pass exactly one of TicketId or TicketKey.' }
if ($TicketKey) {
    if ($TicketKey -notmatch '^[A-Z][A-Z0-9_]+-[0-9]+$') { throw 'Invalid Jira ticket key.' }
    $ticketMatches = (Invoke-RestMethod -Method Get -Uri "$ApiUrl/api/tickets?key=$TicketKey").data
    if (@($ticketMatches).Count -ne 1) { throw 'Ticket key was not found or is ambiguous; use TicketId.' }
    $TicketId = $ticketMatches[0].id
}
if ($TicketId -notmatch '^[0-9a-fA-F-]{36}$') { throw 'TicketId must be a UUID.' }
$result = Invoke-RestMethod -Method Get -Uri "$ApiUrl/api/tickets/$TicketId/history"
$result | ConvertTo-Json -Depth 20
