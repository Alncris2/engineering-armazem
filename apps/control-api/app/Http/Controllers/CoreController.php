<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Routing\Controller;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;

class CoreController extends Controller
{
    private function ok(mixed $data, int $status = 200) { return response()->json(['data' => $data, 'error' => null], $status); }
    private function row(string $table, string $id) { return DB::table($table)->where('id', $id)->first() ?? abort(404); }
    private function insert(string $table, array $data): object
    {
        $data['id'] = (string) Str::uuid();
        $data['created_at'] = $data['updated_at'] = now();
        DB::table($table)->insert($data);
        return $this->row($table, $data['id']);
    }
    private function event(string $runId, string $type, array $payload = []): void
    {
        DB::table('runs')->where('id', $runId)->lockForUpdate()->first();
        $seq = ((int) DB::table('run_events')->where('run_id', $runId)->max('seq')) + 1;
        $this->insert('run_events', ['run_id' => $runId, 'seq' => $seq, 'event_type' => $type,
            'payload' => json_encode($payload), 'occurred_at' => now()]);
    }
    public function projects() { return $this->ok(DB::table('projects')->orderBy('slug')->get()); }
    public function project(string $id)
    {
        $project = $this->row('projects', $id);
        $project->repositories = $this->repositoryRows($id);
        return $this->ok($project);
    }
    public function updateProject(Request $request, string $id)
    {
        $this->row('projects', $id);
        $v = $request->validate(['description' => 'required|string|max:2000']);
        DB::table('projects')->where('id', $id)->update($v + ['updated_at' => now()]);
        return $this->project($id);
    }
    private function repositoryRows(string $projectId)
    {
        return DB::table('repositories')->where('project_id', $projectId)->orderBy('name')->get()
            ->map(function ($repository) {
                $repository->technologies = DB::table('repository_technologies')
                    ->where('repository_id', $repository->id)->orderBy('name')->get();
                return $repository;
            });
    }
    public function repositories(string $id)
    {
        $this->row('projects', $id);
        return $this->ok($this->repositoryRows($id));
    }
    public function createRepository(Request $request, string $id)
    {
        $this->row('projects', $id);
        $v = $request->validate(['name' => 'required|string|max:100',
            'path' => 'required|string|max:1024',
            'role' => ['required', Rule::in(['backend', 'frontend', 'fullstack', 'shared'])]]);
        $path = str_replace('/', '\\', trim($v['path']));
        if (strlen($path) < 4 || !ctype_alpha($path[0]) || $path[1] !== ':' || $path[2] !== '\\'
            || in_array('', explode('\\', substr($path, 3)), true)
            || in_array('.', explode('\\', substr($path, 3)), true)
            || in_array('..', explode('\\', substr($path, 3)), true)
            || preg_match('/[\x00-\x1f]/', $path)) abort(422, 'Path must be an absolute Windows directory without traversal.');
        $v['path'] = strtoupper($path[0]).substr($path, 1);
        $existing = DB::table('repositories')->where('project_id', $id)->where('path', $v['path'])->first();
        if ($existing) {
            if ($existing->name !== $v['name'] || $existing->role !== $v['role']) abort(409, 'Repository path already has different metadata.');
            return $this->ok($existing);
        }
        if (DB::table('repositories')->where('project_id', $id)->where('name', $v['name'])->exists()) abort(409, 'Repository name already has another path.');
        return $this->ok($this->insert('repositories', ['project_id' => $id] + $v), 201);
    }
    public function createTechnology(Request $request, string $id)
    {
        $this->row('repositories', $id);
        $v = $request->validate(['name' => 'required|string|max:100',
            'role' => ['required', Rule::in(['runtime', 'framework', 'database'])],
            'declared_version' => 'nullable|string|max:100',
            'observed_version' => 'nullable|string|max:100',
            'observed_source' => 'required_with:observed_version|nullable|string|max:255']);
        $existing = DB::table('repository_technologies')->where('repository_id', $id)
            ->where('name', $v['name'])->where('role', $v['role'])->first();
        if ($existing) {
            foreach (['declared_version', 'observed_version', 'observed_source'] as $field) {
                if (($existing->$field ?? null) !== ($v[$field] ?? null)) abort(409, 'Technology already has different metadata.');
            }
            return $this->ok($existing);
        }
        return $this->ok($this->insert('repository_technologies', ['repository_id' => $id] + $v), 201);
    }
    public function createProject(Request $request)
    {
        $v = $request->validate(['slug' => 'required|string|max:100|regex:/^[a-z0-9-]+$/|unique:projects,slug', 'name' => 'required|string|max:255']);
        return $this->ok($this->insert('projects', $v), 201);
    }
    public function createTicket(Request $request)
    {
        $v = $request->validate(['project_id' => 'required|uuid|exists:projects,id', 'site_key' => 'required|string|max:255',
            'ticket_key' => 'required|string|max:100|regex:/^[A-Z][A-Z0-9_]+-[0-9]+$/', 'summary' => 'nullable|string|max:255']);
        $v['provider'] = 'jira';
        $existing = DB::table('tickets')->where('provider', 'jira')->where('site_key', $v['site_key'])->where('ticket_key', $v['ticket_key'])->first();
        if ($existing && $existing->project_id !== $v['project_id']) abort(409, 'Ticket already belongs to another project.');
        if ($existing) return $this->ok($existing);
        return $this->ok($this->insert('tickets', $v), 201);
    }
    public function tickets(Request $request)
    {
        $q = DB::table('tickets')->orderBy('ticket_key');
        if ($request->filled('key')) $q->where('ticket_key', $request->query('key'));
        return $this->ok($q->limit(100)->get());
    }
    public function createRun(Request $request)
    {
        $v = $request->validate(['project_id' => 'required|uuid|exists:projects,id', 'ticket_id' => 'nullable|uuid|exists:tickets,id',
            'pipeline_id' => 'required|string|max:100', 'client_request_key' => 'required|string|max:255']);
        if (!empty($v['ticket_id']) && DB::table('tickets')->where('id', $v['ticket_id'])->value('project_id') !== $v['project_id']) abort(422, 'Ticket belongs to another project.');
        return DB::transaction(function () use ($v) {
            $existing = DB::table('runs')->where('project_id', $v['project_id'])->where('client_request_key', $v['client_request_key'])->first();
            if ($existing) return $this->ok($existing);
            $run = $this->insert('runs', $v + ['source' => 'workspace', 'status' => 'created']);
            $this->event($run->id, 'run.created');
            return $this->ok($run, 201);
        });
    }
    public function run(string $id)
    {
        $run = $this->row('runs', $id);
        return $this->ok(['run' => $run, 'sessions' => DB::table('executor_sessions')->where('run_id', $id)->get(),
            'artifacts' => DB::table('artifacts')->where('run_id', $id)->get(), 'evidence' => DB::table('evidence')->where('run_id', $id)->get(),
            'decisions' => DB::table('decisions')->where('run_id', $id)->get(), 'events' => DB::table('run_events')->where('run_id', $id)->orderBy('seq')->get()]);
    }
    public function createSession(Request $request, string $id)
    {
        $this->row('runs', $id);
        $v = $request->validate(['executor' => ['required', Rule::in(['claude','codex'])],
            'external_session_id' => 'nullable|uuid',
            'capture_method' => ['nullable', Rule::in(['codex:env+session-meta', 'codex:exec-json', 'claude:env', 'claude:print-json'])]]);
        $hasExternalId = !empty($v['external_session_id']);
        if ($hasExternalId !== !empty($v['capture_method'])) abort(422, 'External session ID and capture method must be provided together.');
        if ($hasExternalId && !str_starts_with($v['capture_method'], $v['executor'].':')) abort(422, 'Capture method does not match executor.');
        if ($hasExternalId) {
            $existing = DB::table('executor_sessions')->where('executor', $v['executor'])
                ->where('external_session_id', $v['external_session_id'])->first();
            if ($existing) {
                if ($existing->run_id !== $id || $existing->capture_method !== $v['capture_method']) abort(409, 'Session is already registered with another run or capture method.');
                return $this->ok($existing);
            }
        }
        return $this->ok($this->insert('executor_sessions', ['run_id' => $id] + $v), 201);
    }
    public function createArtifact(Request $request, string $id)
    {
        $this->row('runs', $id);
        $v = $request->validate(['relative_path' => 'required|string|max:1024', 'kind' => 'required|string|max:100',
            'sha256' => 'required|regex:/^[a-f0-9]{64}$/', 'size_bytes' => 'required|integer|min:0']);
        if (str_contains(str_replace('\\', '/', $v['relative_path']), '../') || str_starts_with($v['relative_path'], '/') || preg_match('/^[A-Za-z]:/', $v['relative_path'])) abort(422, 'Invalid relative path.');
        return DB::transaction(function () use ($id, $v) {
            $a = $this->insert('artifacts', ['run_id' => $id] + $v);
            $this->event($id, 'artifact.recorded', ['artifact_id' => $a->id]);
            return $this->ok($a, 201);
        });
    }
    public function createEvidence(Request $request, string $id)
    {
        $this->row('runs', $id);
        $v = $request->validate(['artifact_id' => 'nullable|uuid|exists:artifacts,id', 'source' => 'required|string|max:100',
            'claim' => 'required|string|max:10000', 'observed_at' => 'nullable|date']);
        if (!empty($v['artifact_id']) && DB::table('artifacts')->where('id', $v['artifact_id'])->value('run_id') !== $id) abort(422, 'Artifact belongs to another run.');
        return DB::transaction(function () use ($id, $v) {
            $e = $this->insert('evidence', ['run_id' => $id] + $v);
            $this->event($id, 'evidence.recorded', ['evidence_id' => $e->id]);
            return $this->ok($e, 201);
        });
    }
    public function ticketHistory(string $id)
    {
        $ticket = $this->row('tickets', $id);
        $runs = DB::table('runs')->where('ticket_id', $id)->orderBy('created_at')->get();
        return $this->ok(['ticket' => $ticket, 'runs' => $runs->map(fn ($r) => $this->runData($r))]);
    }
    public function searchMemory(Request $request)
    {
        $v = $request->validate(['q' => 'required|string|min:2|max:100']);
        $term = '%'.addcslashes($v['q'], '%_\\').'%';
        $tickets = DB::table('tickets')->where('ticket_key', 'like', $term)
            ->orWhere('summary', 'like', $term)->limit(25)->get()
            ->map(fn ($row) => ['type' => 'ticket', 'ticket_id' => $row->id, 'project_id' => $row->project_id,
                'ticket_key' => $row->ticket_key, 'summary' => $row->summary]);
        $evidence = DB::table('evidence')->join('runs', 'runs.id', '=', 'evidence.run_id')
            ->where('evidence.claim', 'like', $term)->select('evidence.id', 'evidence.run_id',
                'evidence.claim', 'runs.ticket_id', 'runs.project_id')->limit(25)->get()
            ->map(fn ($row) => ['type' => 'evidence', 'id' => $row->id, 'run_id' => $row->run_id,
                'ticket_id' => $row->ticket_id, 'project_id' => $row->project_id,
                'claim' => $row->claim]);
        return $this->ok($tickets->concat($evidence)->values());
    }
    private function runData(object $r): array
    {
        $id = $r->id;
        return ['run' => $r, 'sessions' => DB::table('executor_sessions')->where('run_id', $id)->get(),
            'artifacts' => DB::table('artifacts')->where('run_id', $id)->get(), 'evidence' => DB::table('evidence')->where('run_id', $id)->get(),
            'decisions' => DB::table('decisions')->where('run_id', $id)->get(), 'events' => DB::table('run_events')->where('run_id', $id)->orderBy('seq')->get()];
    }
}
