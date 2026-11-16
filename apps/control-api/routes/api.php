<?php

use App\Http\Controllers\CoreController;
use Illuminate\Support\Facades\Route;

Route::get('/projects', [CoreController::class, 'projects']);
Route::post('/projects', [CoreController::class, 'createProject']);
Route::get('/projects/{id}', [CoreController::class, 'project']);
Route::patch('/projects/{id}', [CoreController::class, 'updateProject']);
Route::get('/projects/{id}/repositories', [CoreController::class, 'repositories']);
Route::post('/projects/{id}/repositories', [CoreController::class, 'createRepository']);
Route::post('/repositories/{id}/technologies', [CoreController::class, 'createTechnology']);
Route::post('/tickets', [CoreController::class, 'createTicket']);
Route::get('/tickets', [CoreController::class, 'tickets']);
Route::get('/tickets/{id}/history', [CoreController::class, 'ticketHistory']);
Route::post('/runs', [CoreController::class, 'createRun']);
Route::get('/runs/{id}', [CoreController::class, 'run']);
Route::post('/runs/{id}/sessions', [CoreController::class, 'createSession']);
Route::post('/runs/{id}/artifacts', [CoreController::class, 'createArtifact']);
Route::post('/runs/{id}/evidence', [CoreController::class, 'createEvidence']);
Route::get('/memory/search', [CoreController::class, 'searchMemory']);
