<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('workflow_leases', function (Blueprint $table): void {
            $table->string('resource', 255)->primary();
            $table->foreignUuid('run_id')->unique()->constrained('runs')->cascadeOnDelete();
            $table->timestampsTz();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('workflow_leases');
    }
};
