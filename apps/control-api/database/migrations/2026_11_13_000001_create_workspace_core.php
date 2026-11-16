<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('projects', function (Blueprint $t) {
            $t->uuid('id')->primary(); $t->string('slug')->unique(); $t->string('name'); $t->timestampsTz();
        });
        Schema::create('repositories', function (Blueprint $t) {
            $t->uuid('id')->primary(); $t->foreignUuid('project_id')->constrained()->cascadeOnDelete();
            $t->string('name'); $t->string('path'); $t->string('role')->nullable(); $t->timestampsTz();
            $t->unique(['project_id', 'name']);
        });
        Schema::create('tickets', function (Blueprint $t) {
            $t->uuid('id')->primary(); $t->foreignUuid('project_id')->constrained();
            $t->string('provider'); $t->string('site_key'); $t->string('ticket_key');
            $t->string('summary')->nullable(); $t->timestampsTz();
            $t->unique(['provider', 'site_key', 'ticket_key']); $t->index('project_id');
        });
        Schema::create('runs', function (Blueprint $t) {
            $t->uuid('id')->primary(); $t->foreignUuid('project_id')->constrained();
            $t->foreignUuid('ticket_id')->nullable()->constrained(); $t->string('source')->default('workspace');
            $t->string('source_squad')->nullable(); $t->string('source_run_id')->nullable(); $t->string('pipeline_id'); $t->string('status');
            $t->string('state_path')->nullable(); $t->string('client_request_key')->nullable(); $t->timestampsTz();
            $t->unique(['project_id', 'source', 'source_squad', 'source_run_id']);
            $t->unique(['project_id', 'client_request_key']); $t->index(['ticket_id', 'created_at']);
        });
        Schema::create('executor_sessions', function (Blueprint $t) {
            $t->uuid('id')->primary(); $t->foreignUuid('run_id')->constrained()->cascadeOnDelete();
            $t->string('executor'); $t->string('external_session_id')->nullable();
            $t->string('capture_method')->nullable(); $t->string('status')->default('recorded');
            $t->timestampsTz(); $t->unique(['executor', 'external_session_id']);
        });
        Schema::create('artifacts', function (Blueprint $t) {
            $t->uuid('id')->primary(); $t->foreignUuid('run_id')->constrained()->cascadeOnDelete();
            $t->string('relative_path'); $t->string('kind'); $t->string('sha256', 64);
            $t->unsignedBigInteger('size_bytes'); $t->timestampsTz(); $t->unique(['run_id', 'relative_path']);
        });
        Schema::create('evidence', function (Blueprint $t) {
            $t->uuid('id')->primary(); $t->foreignUuid('run_id')->constrained()->cascadeOnDelete();
            $t->foreignUuid('artifact_id')->nullable()->constrained('artifacts')->nullOnDelete();
            $t->string('source'); $t->text('claim'); $t->timestampTz('observed_at')->nullable(); $t->timestampsTz();
            $t->index(['run_id', 'created_at']);
        });
        Schema::create('decisions', function (Blueprint $t) {
            $t->uuid('id')->primary(); $t->foreignUuid('run_id')->constrained()->cascadeOnDelete();
            $t->string('kind'); $t->text('rationale'); $t->string('actor')->nullable(); $t->timestampsTz();
            $t->index(['run_id', 'created_at']);
        });
        Schema::create('run_events', function (Blueprint $t) {
            $t->uuid('id')->primary(); $t->foreignUuid('run_id')->constrained()->cascadeOnDelete();
            $t->unsignedInteger('seq'); $t->string('event_type'); $t->string('source_event_key')->nullable();
            $t->json('payload')->nullable(); $t->timestampTz('occurred_at'); $t->timestampsTz();
            $t->unique(['run_id', 'seq']); $t->unique(['run_id', 'source_event_key']);
        });
    }

    public function down(): void
    {
        foreach (['run_events','decisions','evidence','artifacts','executor_sessions','runs','tickets','repositories','projects'] as $table) Schema::dropIfExists($table);
    }
};
