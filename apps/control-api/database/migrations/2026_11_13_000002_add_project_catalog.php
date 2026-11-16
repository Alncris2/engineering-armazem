<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::table('projects', function (Blueprint $table): void {
            $table->text('description')->nullable();
        });

        Schema::table('repositories', function (Blueprint $table): void {
            $table->unique(['project_id', 'path']);
        });

        Schema::create('repository_technologies', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->foreignUuid('repository_id')->constrained('repositories')->cascadeOnDelete();
            $table->string('name', 100);
            $table->string('role', 40);
            $table->string('declared_version', 100)->nullable();
            $table->string('observed_version', 100)->nullable();
            $table->string('observed_source', 255)->nullable();
            $table->timestampsTz();
            $table->unique(['repository_id', 'name', 'role']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('repository_technologies');
        Schema::table('repositories', function (Blueprint $table): void {
            $table->dropUnique(['project_id', 'path']);
        });
        Schema::table('projects', function (Blueprint $table): void {
            $table->dropColumn('description');
        });
    }
};
