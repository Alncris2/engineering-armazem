<?php

return [
    'name' => env('APP_NAME', 'AI Engineering Workspace'), 'env' => env('APP_ENV', 'production'),
    'debug' => (bool) env('APP_DEBUG', false), 'url' => env('APP_URL', 'http://127.0.0.1:8088'),
    'timezone' => 'UTC', 'locale' => 'en', 'fallback_locale' => 'en', 'faker_locale' => 'en_US',
    'key' => env('APP_KEY'), 'cipher' => 'AES-256-CBC',
];
