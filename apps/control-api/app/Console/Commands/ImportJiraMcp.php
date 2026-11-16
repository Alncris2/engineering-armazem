<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;

class ImportJiraMcp extends Command
{
    protected $signature = 'workspace:import-jira-snapshot {project} {site} {key} {--file= : Normalized JSON from a Jira read} {--stdin : Read normalized JSON from standard input}';
    protected $aliases = ['workspace:import-jira-mcp'];
    protected $description = 'Import validated Jira metadata from a read-only source';

    public function handle(): int
    {
        $path = $this->option('file');
        $fromStdin = (bool) $this->option('stdin');
        if ($fromStdin === (bool) $path) return $this->importError('Choose exactly one of --file or --stdin.');
        if (!$fromStdin && (!is_file($path) || is_link($path) || filesize($path) > 1048576)) {
            return $this->importError('Provide a regular JSON file of at most 1 MiB with --file.');
        }
        try {
            $json = $fromStdin ? stream_get_contents(STDIN, 1048577) : file_get_contents($path);
            if ($json === false || strlen($json) > 1048576) return $this->importError('Snapshot exceeds 1 MiB or cannot be read.');
            $snapshot = json_decode($json, true, 16, JSON_THROW_ON_ERROR);
        } catch (\Throwable) {
            return $this->importError('Invalid JSON snapshot.');
        }
        if (!is_array($snapshot) || array_is_list($snapshot)) return $this->importError('Snapshot must be a JSON object.');
        if (array_diff(array_keys($snapshot), ['site', 'key', 'issue_id', 'summary', 'status', 'updated_at'])) {
            return $this->importError('Snapshot contains unsupported fields.');
        }
        $site = strtolower($this->argument('site'));
        $key = $this->argument('key');
        if (!preg_match('/^[a-z0-9.-]+\.atlassian\.net$/', $site)
            || !preg_match('/^[A-Z][A-Z0-9_]+-[0-9]+$/', $key)) return $this->importError('Invalid Jira site or ticket key.');
        $validator = Validator::make($snapshot, [
            'site' => ['required', 'string', 'max:255'],
            'key' => ['required', 'string', 'regex:/^[A-Z][A-Z0-9_]+-[0-9]+$/'],
            'issue_id' => ['required', 'string', 'max:100', 'regex:/^[0-9]+$/'],
            'summary' => ['required', 'string', 'max:255'],
            'status' => ['required', 'string', 'max:100'],
            'updated_at' => ['required', 'date'],
        ]);
        if ($validator->fails() || strtolower($snapshot['site'] ?? '') !== $site || ($snapshot['key'] ?? null) !== $key) {
            return $this->importError('Snapshot identity or fields are invalid.');
        }
        $project = DB::table('projects')->where('slug', $this->argument('project'))->first();
        if (!$project) return $this->importError('Project not found.');
        $data = $validator->validated();
        $updated = date('Y-m-d H:i:sP', strtotime($data['updated_at']));
        $metadata = [
            'summary' => $data['summary'],
            'jira_issue_id' => $data['issue_id'],
            'jira_status' => $data['status'],
            'jira_updated_at' => $updated,
        ];
        $hash = hash('sha256', json_encode([$site, $key, $metadata], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
        $result = DB::transaction(function () use ($project, $site, $key, $metadata, $hash) {
            $ticket = DB::table('tickets')->where('provider', 'jira')->where('site_key', $site)
                ->where('ticket_key', $key)->lockForUpdate()->first();
            if ($ticket && $ticket->project_id !== $project->id) return ['error' => 'Ticket belongs to another project.'];
            if ($ticket && $ticket->jira_issue_id && $ticket->jira_issue_id !== $metadata['jira_issue_id']) {
                return ['error' => 'Jira issue ID differs from the previously imported issue.'];
            }
            if ($ticket && $ticket->jira_updated_at && strtotime($metadata['jira_updated_at']) < strtotime($ticket->jira_updated_at)) {
                return ['error' => 'Snapshot is older than the stored Jira version.'];
            }
            if ($ticket && $ticket->jira_payload_hash === $hash) return ['id' => $ticket->id, 'action' => 'unchanged'];
            $now = now();
            if ($ticket) {
                DB::table('tickets')->where('id', $ticket->id)->update($metadata + [
                    'jira_payload_hash' => $hash, 'jira_fetched_at' => $now, 'updated_at' => $now,
                ]);
                return ['id' => $ticket->id, 'action' => 'updated'];
            }
            $id = (string) Str::uuid();
            DB::table('tickets')->insert([
                'id' => $id, 'project_id' => $project->id, 'provider' => 'jira',
                'site_key' => $site, 'ticket_key' => $key,
            ] + $metadata + ['jira_payload_hash' => $hash, 'jira_fetched_at' => $now,
                'created_at' => $now, 'updated_at' => $now]);
            return ['id' => $id, 'action' => 'created'];
        });
        if (isset($result['error'])) return $this->importError($result['error']);
        $this->line(json_encode(['ticket_id' => $result['id'], 'ticket_key' => $key, 'action' => $result['action']]));
        return self::SUCCESS;
    }

    private function importError(string $message): int
    {
        $this->error($message);
        return self::FAILURE;
    }
}
