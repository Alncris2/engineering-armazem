param(
    [string]$ApiUrl = 'http://127.0.0.1:8088',
    [string]$CatalogPath = (Join-Path $PSScriptRoot '..\..\config\projects\catalog.json')
)

$ErrorActionPreference = 'Stop'
if ($ApiUrl -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?$') { throw 'The API must use loopback HTTP.' }
$catalog = Get-Content -LiteralPath $CatalogPath -Raw | ConvertFrom-Json
if ($catalog.schema_version -ne 1 -or @($catalog.projects).Count -ne 6) { throw 'Unexpected catalog format or project count.' }

$existing = (Invoke-RestMethod -Method Get -Uri "$ApiUrl/api/projects").data
$bySlug = @{}
foreach ($project in @($existing)) { $bySlug[$project.slug] = $project }

# Check all inputs before the first write.
foreach ($project in $catalog.projects) {
    if (-not $bySlug.ContainsKey($project.slug)) { throw "Project not found: $($project.slug)" }
    $paths = @{}
    foreach ($repository in $project.repositories) {
        if (-not (Test-Path -LiteralPath $repository.path -PathType Container)) { throw "Repository path not found: $($repository.path)" }
        if ($paths.ContainsKey($repository.path)) { throw "Duplicate repository path: $($repository.path)" }
        $paths[$repository.path] = $true
    }
}

$results = @()
foreach ($project in $catalog.projects) {
    $id = $bySlug[$project.slug].id
    if ($bySlug[$project.slug].description -ne $project.description) {
        $body = @{ description = $project.description } | ConvertTo-Json -Compress
        $null = Invoke-RestMethod -Method Patch -Uri "$ApiUrl/api/projects/$id" -ContentType 'application/json' -Body $body
    }
    foreach ($repository in $project.repositories) {
        $body = @{ name = $repository.name; path = $repository.path; role = $repository.role } | ConvertTo-Json -Compress
        $stored = (Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/projects/$id/repositories" -ContentType 'application/json' -Body $body).data
        foreach ($technology in $repository.technologies) {
            $techBody = $technology | ConvertTo-Json -Compress -Depth 5
            $null = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/repositories/$($stored.id)/technologies" -ContentType 'application/json' -Body $techBody
        }
    }
    $detail = (Invoke-RestMethod -Method Get -Uri "$ApiUrl/api/projects/$id").data
    if (@($detail.repositories).Count -ne @($project.repositories).Count) { throw "Repository count mismatch: $($project.slug)" }
    $expectedTechnologies = @($project.repositories | ForEach-Object { @($_.technologies).Count } | Measure-Object -Sum).Sum
    $actualTechnologies = @($detail.repositories | ForEach-Object { @($_.technologies).Count } | Measure-Object -Sum).Sum
    if ($actualTechnologies -ne $expectedTechnologies) { throw "Technology count mismatch: $($project.slug)" }
    $results += [pscustomobject]@{ slug = $project.slug; project_id = $id; repositories = @($detail.repositories).Count; technologies = $actualTechnologies }
}
$results | ConvertTo-Json -Depth 5
