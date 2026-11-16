# OpenSquad read-only adapter

O comando `php artisan workspace:import-opensquad PROJECT_SLUG SQUAD RUN_ID --ticket=EVOLOG-123` lê apenas `squads/SQUAD/output/RUN_ID/state.json` e seus arquivos. `OPENSQUAD_ROOT` define a raiz. O ticket precisa existir na API e pertencer ao projeto. O importador registra hashes e caminhos relativos; não grava no OpenSquad, não chama `route.mjs` e não inicia pipeline.
