$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..\apps\control-api')
Set-Location $root
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env'; Write-Warning 'Set DB credentials in .env before migrations.' }
composer install --no-interaction
if ($LASTEXITCODE -ne 0) { throw 'composer install failed.' }
if (-not (Select-String -LiteralPath '.env' -Pattern '^APP_KEY=.+$' -Quiet)) {
    php -d xdebug.mode=off artisan key:generate
    if ($LASTEXITCODE -ne 0) { throw 'APP_KEY generation failed.' }
}
php -d xdebug.mode=off -r "exit(extension_loaded('pdo_pgsql') ? 0 : 1);"
if ($LASTEXITCODE -ne 0) { throw 'Enable pdo_pgsql in the PHP CLI configuration before migrations.' }
Write-Output 'After configuring PostgreSQL, run: php -d xdebug.mode=off artisan migrate'
