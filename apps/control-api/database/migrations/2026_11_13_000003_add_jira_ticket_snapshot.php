<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::table('tickets', function (Blueprint $table): void {
            $table->string('jira_issue_id', 100)->nullable();
            $table->string('jira_status', 100)->nullable();
            $table->timestampTz('jira_updated_at')->nullable();
            $table->timestampTz('jira_fetched_at')->nullable();
            $table->string('jira_payload_hash', 64)->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('tickets', function (Blueprint $table): void {
            $table->dropColumn(['jira_issue_id', 'jira_status', 'jira_updated_at', 'jira_fetched_at', 'jira_payload_hash']);
        });
    }
};
