<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RecursiveDirectoryIterator;
use RecursiveIteratorIterator;

class ImportOpenSquad extends Command
{
    protected $signature = 'workspace:import-opensquad {project} {squad} {run} {--ticket=}';
    protected $description = 'Import an existing OpenSquad run without changing its files';

    public function handle(): int
    {
        $root = realpath(config('workspace.opensquad_root'));
        $squad = $this->argument('squad'); $sourceId = $this->argument('run');
        if (!$root || !preg_match('/^[a-zA-Z0-9_-]+$/', $squad) || !preg_match('/^[a-zA-Z0-9_-]+$/', $sourceId)) return $this->importError('Invalid root, squad or run ID.');
        $base = realpath($root.DIRECTORY_SEPARATOR.'squads'.DIRECTORY_SEPARATOR.$squad.DIRECTORY_SEPARATOR.'output'.DIRECTORY_SEPARATOR.$sourceId);
        $allowed = realpath($root.DIRECTORY_SEPARATOR.'squads'.DIRECTORY_SEPARATOR.$squad.DIRECTORY_SEPARATOR.'output');
        if (!$base || !$allowed || !str_starts_with(strtolower($base), strtolower($allowed.DIRECTORY_SEPARATOR))) return $this->importError('Run path is outside the OpenSquad output root.');
        $stateFile = $base.DIRECTORY_SEPARATOR.'state.json';
        if (!is_file($stateFile) || is_link($stateFile) || filesize($stateFile) > 1048576) return $this->importError('Archived state.json is missing or invalid.');
        try { $state = json_decode(file_get_contents($stateFile), true, 32, JSON_THROW_ON_ERROR); }
        catch (\Throwable $e) { return $this->importError('Invalid state.json format.'); }
        if (!is_array($state) || ($state['runId'] ?? null) !== $sourceId || ($state['squad'] ?? null) !== $squad || !is_string($state['status'] ?? null) || !is_string($state['pipelineId'] ?? null)) return $this->importError('State identity or required fields do not match.');
        $project = DB::table('projects')->where('slug', $this->argument('project'))->first();
        if (!$project) return $this->importError('Project not found.');
        $ticket = null;
        if ($key = $this->option('ticket')) {
            $ticket = DB::table('tickets')->where('project_id', $project->id)->where('ticket_key', $key)->first();
            if (!$ticket) return $this->importError('Ticket not found in project.');
        }
        $files = [];
        foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($base, \FilesystemIterator::SKIP_DOTS)) as $file) {
            if ($file->isLink() || !$file->isFile()) return $this->importError('Non-regular file found.');
            $path = $file->getRealPath();
            if (!$path || !str_starts_with(strtolower($path), strtolower($base.DIRECTORY_SEPARATOR))) return $this->importError('Artifact path escapes run folder.');
            $relative = str_replace('\\', '/', substr($path, strlen($base) + 1));
            $files[] = ['relative_path' => $relative, 'kind' => pathinfo($relative, PATHINFO_EXTENSION) ?: 'file',
                'sha256' => hash_file('sha256', $path), 'size_bytes' => $file->getSize()];
        }
        $run = DB::transaction(function () use ($project, $ticket, $sourceId, $state, $files, $squad) {
            $run = DB::table('runs')->where('project_id', $project->id)->where('source', 'opensquad')->where('source_squad', $squad)->where('source_run_id', $sourceId)->first();
            if (!$run) {
                $id = (string) Str::uuid(); $now = now();
                DB::table('runs')->insert(['id' => $id, 'project_id' => $project->id, 'ticket_id' => $ticket?->id,
                    'source' => 'opensquad', 'source_squad' => $squad, 'source_run_id' => $sourceId, 'pipeline_id' => $state['pipelineId'],
                    'status' => $state['status'], 'state_path' => "squads/$squad/output/$sourceId/state.json", 'created_at' => $now, 'updated_at' => $now]);
                DB::table('run_events')->insert(['id' => (string) Str::uuid(), 'run_id' => $id, 'seq' => 1,
                    'event_type' => 'run.imported', 'source_event_key' => 'opensquad:import',
                    'payload' => json_encode(['source_run_id' => $sourceId]), 'occurred_at' => $now, 'created_at' => $now, 'updated_at' => $now]);
                $run = DB::table('runs')->where('id', $id)->first();
            } elseif ($ticket && !$run->ticket_id) {
                DB::table('runs')->where('id', $run->id)->update(['ticket_id' => $ticket->id, 'updated_at' => now()]);
            }
            foreach ($files as $file) {
                $existing = DB::table('artifacts')->where('run_id', $run->id)->where('relative_path', $file['relative_path'])->first();
                if ($existing && ($existing->sha256 !== $file['sha256'] || (int) $existing->size_bytes !== $file['size_bytes'])) throw new \RuntimeException('Artifact changed since import: '.$file['relative_path']);
                if (!$existing) DB::table('artifacts')->insert(['id' => (string) Str::uuid(), 'run_id' => $run->id] + $file + ['created_at' => now(), 'updated_at' => now()]);
            }
            return $run;
        });
        $this->line(json_encode(['run_id' => $run->id, 'source_run_id' => $sourceId, 'artifacts_seen' => count($files)]));
        return self::SUCCESS;
    }
    private function importError(string $message): int { $this->error($message); return self::FAILURE; }
}
