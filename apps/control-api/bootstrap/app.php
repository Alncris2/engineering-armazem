<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(api: __DIR__.'/../routes/api.php', commands: __DIR__.'/../routes/console.php', health: '/up')
    ->withCommands([\App\Console\Commands\ImportOpenSquad::class, \App\Console\Commands\ImportJiraMcp::class])
    ->withMiddleware(function (Middleware $middleware): void { $middleware->group('api', []); })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(fn (Request $request) => $request->is('api/*'));
        $exceptions->render(function (\Illuminate\Validation\ValidationException $e, Request $request) {
            if (!$request->is('api/*')) return null;
            return response()->json(['data' => null, 'error' => ['code' => 'VALIDATION_ERROR', 'message' => 'Invalid input.', 'details' => $e->errors()]], 422);
        });
        $exceptions->render(function (\Symfony\Component\HttpKernel\Exception\HttpExceptionInterface $e, Request $request) {
            if (!$request->is('api/*')) return null;
            return response()->json(['data' => null, 'error' => ['code' => 'HTTP_ERROR', 'message' => $e->getMessage() ?: 'Request failed.']], $e->getStatusCode());
        });
    })->create();
