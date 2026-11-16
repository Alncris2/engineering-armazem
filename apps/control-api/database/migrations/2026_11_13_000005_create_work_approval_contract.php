<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('work_approval_credentials', function (Blueprint $t): void {
            $t->uuid('id')->primary();
            $t->string('credential_id_sha256', 64)->unique();
            $t->binary('public_key');
            $t->string('rp_id', 255);
            $t->unsignedBigInteger('sign_count')->default(0);
            $t->string('state', 16)->default('pending');
            $t->timestampTz('registered_at')->nullable();
            $t->timestampTz('revoked_at')->nullable();
            $t->timestampsTz();
            $t->index(['state', 'registered_at']);
        });
        Schema::create('work_approval_challenges', function (Blueprint $t): void {
            $t->uuid('id')->primary();
            $t->unsignedSmallInteger('contract_version');
            $t->string('thread_id', 100);
            $t->string('issue_key', 100);
            $t->string('stage', 16);
            $t->unsignedSmallInteger('attempt');
            $t->string('plan_sha256', 64);
            $t->string('spec_sha256', 64);
            $t->string('repo', 1024);
            $t->string('head', 64);
            $t->string('inventory_sha256', 64);
            $t->json('allowlist');
            $t->string('target_module', 512);
            $t->string('nonce', 64)->unique();
            $t->string('payload_sha256', 64)->unique();
            $t->json('payload');
            $t->string('state', 16)->default('pending');
            $t->timestampTz('issued_at');
            $t->timestampTz('expires_at');
            $t->timestampTz('consumed_at')->nullable();
            $t->timestampsTz();
            $t->unique(['thread_id', 'stage', 'attempt'], 'work_approval_one_challenge_per_attempt');
            $t->index(['state', 'expires_at']);
        });
        Schema::create('work_approvals', function (Blueprint $t): void {
            $t->uuid('id')->primary();
            $t->foreignUuid('challenge_id')->unique()->constrained('work_approval_challenges');
            $t->foreignUuid('credential_id')->nullable()->constrained('work_approval_credentials');
            $t->string('decision', 16);
            $t->string('verifier_kind', 16);
            $t->string('payload_sha256', 64)->unique();
            $t->string('assertion_sha256', 64)->nullable();
            $t->timestampTz('decided_at');
            $t->timestampsTz();
            $t->index(['verifier_kind', 'decision', 'decided_at']);
        });
        foreach ([
            "ALTER TABLE work_approval_credentials ADD CONSTRAINT work_credential_state_check CHECK (state IN ('pending','active','revoked'))",
            "ALTER TABLE work_approval_credentials ADD CONSTRAINT work_credential_hash_check CHECK (length(credential_id_sha256) = 64)",
            "ALTER TABLE work_approval_challenges ADD CONSTRAINT work_challenge_version_check CHECK (contract_version = 1)",
            "ALTER TABLE work_approval_challenges ADD CONSTRAINT work_challenge_stage_check CHECK (stage = 'work' AND attempt = 1)",
            "ALTER TABLE work_approval_challenges ADD CONSTRAINT work_challenge_state_check CHECK (state IN ('pending','consumed','expired'))",
            "ALTER TABLE work_approval_challenges ADD CONSTRAINT work_challenge_time_check CHECK (issued_at < expires_at AND expires_at <= issued_at + interval '5 minutes')",
            "ALTER TABLE work_approval_challenges ADD CONSTRAINT work_challenge_hash_check CHECK (length(plan_sha256) = 64 AND length(spec_sha256) = 64 AND length(inventory_sha256) = 64 AND length(payload_sha256) = 64 AND length(nonce) = 64)",
            "ALTER TABLE work_approvals ADD CONSTRAINT work_approval_decision_check CHECK (decision IN ('approved','rejected'))",
            "ALTER TABLE work_approvals ADD CONSTRAINT work_approval_verifier_check CHECK (verifier_kind = 'webauthn')",
            "ALTER TABLE work_approvals ADD CONSTRAINT work_approval_assertion_check CHECK (decision <> 'approved' OR (credential_id IS NOT NULL AND assertion_sha256 IS NOT NULL))",
            "ALTER TABLE work_approvals ADD CONSTRAINT work_approval_hash_check CHECK (length(payload_sha256) = 64 AND (assertion_sha256 IS NULL OR length(assertion_sha256) = 64))",
        ] as $sql) {
            if (DB::getDriverName() === 'pgsql') {
                DB::statement($sql);
            }
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('work_approvals');
        Schema::dropIfExists('work_approval_challenges');
        Schema::dropIfExists('work_approval_credentials');
    }
};
