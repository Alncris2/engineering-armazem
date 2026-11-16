param([ValidateRange(1, 65535)][int]$Port = 8088)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..\apps\control-api')
Set-Location $root
if (-not (Test-Path '.env')) { throw 'Create apps/control-api/.env from .env.example and set local database credentials.' }
php -d xdebug.mode=off -r "exit(extension_loaded('pdo_pgsql') ? 0 : 1);"
if ($LASTEXITCODE -ne 0) { throw 'Enable pdo_pgsql in the PHP CLI before starting the API.' }
php -d xdebug.mode=off artisan serve --host=127.0.0.1 --port=$Port
