# Workspace Core v1

## Contrato

API Laravel 13 em loopback; PostgreSQL para projects, repositories, tickets, runs, executor_sessions, artifacts, evidence, decisions e run_events. IDs internos UUID. O importador de OpenSquad lê snapshots arquivados e registra somente metadados e hashes. Claude Code e Codex consultam o mesmo histórico pelo script PowerShell `scripts/windows/history.ps1`, em uma sessão nova no Maestri.

## Instalação Windows

1. Ajuste `apps/control-api/.env` a partir de `.env.example`, sem versionar o arquivo. Configure banco e senha localmente.
2. Execute `pwsh -File scripts/windows/install.ps1` na raiz do monorepositório. O script instala as versões fixadas em `composer.lock`, cria `.env` se necessário, gera `APP_KEY` apenas se estiver vazia e verifica `pdo_pgsql` no PHP CLI.
3. Crie o banco e habilite `CREATE EXTENSION IF NOT EXISTS vector` com uma conta autorizada. Confirme `SELECT extversion FROM pg_extension WHERE extname='vector'`.
4. Execute em `apps/control-api`: `php -d xdebug.mode=off artisan migrate`.
5. Execute `scripts/windows/start-api.ps1`. O servidor `artisan serve` é apenas para uso local interativo.

## Exemplo de fluxo

`POST /api/projects` recebe `{"slug":"webagil","name":"WebAgil"}`. `POST /api/tickets` recebe `{"project_id":"UUID","site_key":"jira-local","ticket_key":"EVOLOG-31599"}`. `POST /api/runs` recebe `project_id`, `ticket_id`, `pipeline_id` e `client_request_key`. `GET /api/tickets/{uuid}/history` reúne runs, sessões, artefatos, evidências, decisões e eventos.

O catálogo de projetos passou a incluir descrições, repositórios e tecnologias. Endpoints, sincronização dos seis projetos e diferenças entre versões declaradas e observadas estão em [project-catalog.md](project-catalog.md).

A leitura e importação de metadados pelo Jira MCP existente estão em [jira-mcp.md](jira-mcp.md). O fluxo foi testado com `EVOLOG-31599` sem alterar o OpenSquad.

Depois de cadastrar projeto e ticket, importe uma run existente com `php artisan workspace:import-opensquad webagil webagil-dev 2026-11-12-evolog-31599-support --ticket=EVOLOG-31599`. Repetir o comando não duplica run nem artefatos. Uma mudança de conteúdo no mesmo caminho bloqueia a importação e requer revisão.

## Registro nos executores

No Maestri, abra um terminal Claude Code ou Codex no diretório deste workspace e instrua o agente a usar `pwsh -File scripts/windows/history.ps1 -TicketKey EVOLOG-31599` ao consultar um chamado. Também aceita `-TicketId UUID`. O script usa somente HTTP loopback. O procedimento para registrar IDs de sessão capturados está em [session-capture.md](session-capture.md).

## Limites

O CLI do Maestri nesta sessão não recebeu `MAESTRI_PIPE`, então presets e agentes conectados não puderam ser inspecionados nem configurados. Em atualização posterior, a conexão ao PostgreSQL, o pgvector 0.8.7 e a migration foram confirmados; ver [validation-core-v1.md](validation-core-v1.md). A API não tem autenticação multiusuário; mantenha-a apenas em loopback. O importador exige `state.json` arquivado na pasta da run; estados apenas globais não são importados.

O `composer.lock` foi gerado e uma instalação limpa em pasta temporária passou nos testes automatizados. A primeira tentativa sem autorização de rede esbarrou no proxy desta sessão; uma execução com acesso ao Packagist concluiu o download. O fluxo HTTP foi demonstrado em SQLite temporário e, posteriormente, o cadastro de projeto, ticket, importação idempotente e histórico foram verificados no PostgreSQL. Veja [validation-core-v1.md](validation-core-v1.md).
