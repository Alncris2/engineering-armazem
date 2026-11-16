<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use RuntimeException;
use Tests\TestCase;

class TicketFilterTest extends TestCase
{
    use RefreshDatabase;

    public function createApplication()
    {
        $app = parent::createApplication();

        if (config('database.default') !== 'sqlite'
            || config('database.connections.sqlite.database') !== ':memory:') {
            throw new RuntimeException('Ticket filter tests require isolated in-memory SQLite.');
        }

        return $app;
    }

    public function test_ticket_key_filter_returns_only_the_exact_ticket_in_the_json_envelope(): void
    {
        $projectId = $this->postJson('/api/projects', ['slug' => 'webagil', 'name' => 'WebAgil'])
            ->assertCreated()->json('data.id');
        $ticketId = $this->postJson('/api/tickets', [
            'project_id' => $projectId, 'site_key' => 'evolog.atlassian.net', 'ticket_key' => 'EVOLOG-33092',
        ])->assertCreated()->json('data.id');
        $this->postJson('/api/tickets', [
            'project_id' => $projectId, 'site_key' => 'evolog.atlassian.net', 'ticket_key' => 'EVOLOG-330920',
        ])->assertCreated();

        $response = $this->getJson('/api/tickets?key=EVOLOG-33092')->assertOk()
            ->assertJsonStructure(['data', 'error'])
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.id', $ticketId)
            ->assertJsonPath('data.0.ticket_key', 'EVOLOG-33092');

        $this->assertSame(null, $response->json('error'));
        $this->assertIsArray($response->json('data'));
        $this->getJson('/api/tickets?key=EVOLOG-3309')->assertOk()
            ->assertJsonStructure(['data', 'error'])
            ->assertJsonCount(0, 'data')
            ->assertJsonPath('error', null);
    }

    public function test_unfiltered_ticket_list_keeps_the_json_envelope_and_key_order(): void
    {
        $projectId = $this->postJson('/api/projects', ['slug' => 'webagil', 'name' => 'WebAgil'])
            ->assertCreated()->json('data.id');
        foreach (['EVOLOG-33092', 'EVOLOG-31599'] as $key) {
            $this->postJson('/api/tickets', [
                'project_id' => $projectId, 'site_key' => 'evolog.atlassian.net', 'ticket_key' => $key,
            ])->assertCreated();
        }

        $response = $this->getJson('/api/tickets')->assertOk()
            ->assertJsonStructure(['data', 'error'])
            ->assertJsonCount(2, 'data');

        $this->assertSame(['EVOLOG-31599', 'EVOLOG-33092'], array_column($response->json('data'), 'ticket_key'));
        $this->assertSame(null, $response->json('error'));
    }
}
