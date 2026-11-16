<?php

use Illuminate\Support\Facades\Artisan;

Artisan::command('workspace:ping', function () { $this->info('workspace-core-ready'); });
