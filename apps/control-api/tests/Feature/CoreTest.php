<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class CoreTest extends TestCase
{
    use RefreshDatabase;

    public function test_project_catalog_records_repositories_and_versions(): void
    {
        $project = $this->postJson('/api/projects', ['slug' => 'fastapi', 'name' => 'fastapi'])->assertCreated()->json('data.id');
        $this->patchJson("/api/projects/$project", ['description' => 'Python service with Oracle'])->assertOk();
        $path = 'C:\\htdocs\\fastapi';
        $body = ['name' => 'fastapi', 'path' => $path, 'role' => 'backend'];
        $repository = $this->postJson("/api/projects/$project/repositories", $body)->assertCreated()->json('data.id');
        $this->postJson("/api/projects/$project/repositories", $body)->assertOk()->assertJsonPath('data.id', $repository);
        $this->postJson("/api/projects/$project/repositories", ['name' => 'escape', 'path' => 'C:\\htdocs\\..\\secret', 'role' => 'backend'])->assertStatus(422);
        $technology = ['name' => 'Python', 'role' => 'runtime', 'declared_version' => '3.7.4',
            'observed_version' => '3.10.8', 'observed_source' => '.python-version'];
        $this->postJson("/api/repositories/$repository/technologies", $technology)->assertCreated();
        $this->postJson("/api/repositories/$repository/technologies", $technology)->assertOk();
        $this->getJson("/api/projects/$project")->assertOk()
            ->assertJsonPath('data.repositories.0.path', $path)
            ->assertJsonPath('data.repositories.0.technologies.0.declared_version', '3.7.4')
            ->assertJsonPath('data.repositories.0.technologies.0.observed_version', '3.10.8');
        $this->assertSame(1, DB::table('repositories')->count());
        $this->assertSame(1, DB::table('repository_technologies')->count());
    }

    public function test_ticket_history_and_run_idempotency(): void
    {
        $project = $this->postJson('/api/projects', ['slug' => 'webagil', 'name' => 'WebAgil'])->assertCreated()->json('data.id');
        $this->postJson('/api/projects', ['slug' => 'Invalid Slug', 'name' => 'Bad'])->assertStatus(422)->assertJsonPath('error.code', 'VALIDATION_ERROR');
        $ticket = $this->postJson('/api/tickets', ['project_id' => $project, 'site_key' => 'local', 'ticket_key' => 'EVOLOG-31599'])->assertCreated()->json('data.id');
        $this->getJson('/api/memory/search?q=EVOLOG-31599')->assertOk()->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.ticket_id', $ticket);
        $body = ['project_id' => $project, 'ticket_id' => $ticket, 'pipeline_id' => 'support', 'client_request_key' => 'test-1'];
        $run = $this->postJson('/api/runs', $body)->assertCreated()->json('data.id');
        $this->postJson('/api/runs', $body)->assertOk()->assertJsonPath('data.id', $run);
        $this->postJson("/api/runs/$run/sessions", ['executor' => 'codex', 'external_session_id' => 'made-up'])->assertStatus(422);
        $this->postJson("/api/runs/$run/sessions", ['executor' => 'codex'])->assertCreated();
        $external = (string) \Illuminate\Support\Str::uuid();
        $capture = ['executor' => 'codex', 'external_session_id' => $external, 'capture_method' => 'codex:env+session-meta'];
        $session = $this->postJson("/api/runs/$run/sessions", $capture)->assertCreated()->json('data.id');
        $this->postJson("/api/runs/$run/sessions", $capture)->assertOk()->assertJsonPath('data.id', $session);
        $otherRun = $this->postJson('/api/runs', ['project_id' => $project, 'pipeline_id' => 'other', 'client_request_key' => 'test-2'])->assertCreated()->json('data.id');
        $this->postJson("/api/runs/$otherRun/sessions", $capture)->assertStatus(409);
        $this->postJson("/api/runs/$run/sessions", ['executor' => 'claude', 'external_session_id' => (string) \Illuminate\Support\Str::uuid(), 'capture_method' => 'codex:exec-json'])->assertStatus(422);
        $this->getJson("/api/tickets/$ticket/history")->assertOk()->assertJsonPath('data.runs.0.run.id', $run);
        $this->getJson("/api/tickets/$ticket/history")->assertJsonPath('data.runs.0.sessions.1.external_session_id', $external);
        $this->assertSame(2, DB::table('runs')->count());
    }

    public function test_opensquad_import_is_read_only_and_idempotent(): void
    {
        $project = $this->postJson('/api/projects', ['slug' => 'webagil', 'name' => 'WebAgil'])->json('data.id');
        $ticket = $this->postJson('/api/tickets', ['project_id' => $project, 'site_key' => 'local', 'ticket_key' => 'EVOLOG-31599'])->json('data.id');
        $root = sys_get_temp_dir().DIRECTORY_SEPARATOR.'workspace-test-'.bin2hex(random_bytes(5));
        $runDir = $root.'/squads/webagil-dev/output/run-1';
        mkdir($runDir, 0777, true);
        $state = json_encode(['runId' => 'run-1', 'squad' => 'webagil-dev', 'status' => 'completed', 'pipelineId' => 'support']);
        file_put_contents($runDir.'/state.json', $state); file_put_contents($runDir.'/report.md', 'evidence');
        config(['workspace.opensquad_root' => $root]);
        try {
            $this->artisan('workspace:import-opensquad', ['project' => 'webagil', 'squad' => 'webagil-dev', 'run' => 'run-1', '--ticket' => 'EVOLOG-31599'])->assertExitCode(0);
            $this->artisan('workspace:import-opensquad', ['project' => 'webagil', 'squad' => 'webagil-dev', 'run' => 'run-1', '--ticket' => 'EVOLOG-31599'])->assertExitCode(0);
            $this->assertSame(1, DB::table('runs')->count()); $this->assertSame(2, DB::table('artifacts')->count());
            $this->assertSame($state, file_get_contents($runDir.'/state.json'));
            $this->getJson("/api/tickets/$ticket/history")->assertOk()->assertJsonCount(1, 'data.runs');
        } finally { unlink($runDir.'/state.json'); unlink($runDir.'/report.md'); rmdir($runDir); rmdir(dirname($runDir)); rmdir(dirname(dirname($runDir))); rmdir(dirname(dirname(dirname($runDir)))); rmdir($root); }
    }

    public function test_jira_mcp_snapshot_updates_existing_ticket_without_duplication(): void
    {
        $project = $this->postJson('/api/projects', ['slug' => 'webagil', 'name' => 'WebAgil'])->json('data.id');
        $ticket = $this->postJson('/api/tickets', ['project_id' => $project, 'site_key' => 'evolog.atlassian.net',
            'ticket_key' => 'EVOLOG-31599'])->json('data.id');
        $file = tempnam(sys_get_temp_dir(), 'jira-mcp-');
        $snapshot = ['site' => 'evolog.atlassian.net', 'key' => 'EVOLOG-31599', 'issue_id' => '123456',
            'summary' => 'Investigação de suporte', 'status' => 'Em andamento', 'updated_at' => '2026-11-13T10:00:00Z'];
        $args = ['project' => 'webagil', 'site' => 'evolog.atlassian.net', 'key' => 'EVOLOG-31599', '--file' => $file];
        try {
            file_put_contents($file, json_encode($snapshot));
            $this->artisan('workspace:import-jira-mcp', $args)->assertExitCode(0);
            $first = DB::table('tickets')->where('id', $ticket)->first();
            $this->assertSame('Investigação de suporte', $first->summary);
            $this->assertSame('Em andamento', $first->jira_status);
            $this->artisan('workspace:import-jira-mcp', $args)->assertExitCode(0);
            $this->assertSame($first->updated_at, DB::table('tickets')->where('id', $ticket)->value('updated_at'));
            $this->assertSame(1, DB::table('tickets')->count());
            $this->getJson("/api/tickets/$ticket/history")->assertOk()
                ->assertJsonPath('data.ticket.jira_issue_id', '123456');
            file_put_contents($file, json_encode($snapshot + ['unexpected' => 'ignored']));
            $this->artisan('workspace:import-jira-mcp', $args)->assertExitCode(1);
            file_put_contents($file, json_encode(array_replace($snapshot, ['issue_id' => '999999'])));
            $this->artisan('workspace:import-jira-mcp', $args)->assertExitCode(1);
            file_put_contents($file, json_encode(array_replace($snapshot, ['updated_at' => '2026-11-12T10:00:00Z'])));
            $this->artisan('workspace:import-jira-mcp', $args)->assertExitCode(1);
            file_put_contents($file, json_encode($snapshot));
            $this->artisan('workspace:import-jira-mcp', ['project' => 'webagil', 'site' => 'evolog.atlassian.net',
                'key' => 'EVOLOG-99999', '--file' => $file])->assertExitCode(1);
            $this->assertSame(1, DB::table('tickets')->count());
        } finally {
            unlink($file);
        }
    }
}
