# Validação Core v1 — 2026-11-13

## Discovery

Windows nativo; PHP 8.5.12, Composer 2.10.3, Python 3.13.7, Node 25.2.1, PostgreSQL 18.7 e Git 2.55.0.windows.5. PostgreSQL está ativo. `vector.control` e `vector.dll` existem na instalação 18, mas `psql -w` retornou `fe_sendauth: no password supplied`; a extensão não foi confirmada por SQL. O PHP possui DLLs `pdo_pgsql` e `pgsql`, carregadas com `-d extension=...` somente nos processos de teste.

O OpenSquad gera `run_id` no formato de data e hora, com sufixo em colisões; grava estado em `squads/{squad}/state.json` e arquiva uma cópia em `output/{run_id}/state.json` ao concluir. Artefatos vão a `output/{run_id}`, com versões. O CLI do Maestri exige `MAESTRI_PIPE`, ausente nesta sessão; delegação a agentes conectados não pôde ser executada.

## Execução

- `php artisan workspace:ping`: `workspace-core-ready`.
- `phpunit`: 2 testes aprovados, 19 asserções; cobertura de API, erro padronizado, idempotência, importação e leitura sem escrita da origem.
- `php artisan migrate --force` em SQLite temporário: migration `2026_11_13_000001_create_workspace_core` executou.
- Importação da run real `2026-11-12-evolog-31599-support` duas vezes em SQLite temporário: mesmo UUID de run nas duas chamadas e cinco arquivos encontrados.
- Em novo processo PowerShell, `history.ps1 -TicketKey EVOLOG-31599` retornou um ticket, uma run e cinco artefatos via HTTP loopback.
- Nenhum comando de escrita foi dirigido a `C:\htdocs\squad-ia`.

## Limites de aceite

Na validação inicial, PostgreSQL conectado, migration em PostgreSQL e pgvector ainda não tinham prova; a atualização abaixo encerra esses pontos. A instalação limpa do Laravel pelo Composer falhou por proxy indisponível; `vendor/` local ignorado pelo Git permitiu os testes. O CLI do Maestri não pôde listar agentes nesta sessão. Nenhuma credencial foi criada no repositório. Não houve commit porque o perfil permite leitura, mas não escrita em `.git`.

## Atualização — PostgreSQL

Em 2026-11-13, nova sessão confirmou a conexão `pgsql` ao banco local `ai_engineering_workspace` na porta 5432. `pg_available_extensions` retornou pgvector 0.8.7 como instalado. `php artisan migrate --force` criou a tabela de migrations e executou `2026_11_13_000001_create_workspace_core` com sucesso. `migrate:status` mostrou batch 1 / Ran. Consulta ao catálogo confirmou as nove tabelas do Core e dez foreign keys. Nenhuma credencial foi impressa ou gravada na documentação. Os testes automatizados anteriores continuam sendo os de SQLite; não houve reteste funcional HTTP em PostgreSQL nesta atualização.

## Atualização — cadastro de projetos

Um agente no Maestri relatou `GET /api/projects` inicial com HTTP 200 e lista vazia, seis `POST` concluídos e `GET` final com HTTP 200, seis slugs e nenhum duplicado. Consulta independente somente leitura ao PostgreSQL confirmou os slugs `webagil`, `server`, `warehouse`, `lms`, `agend-node` e `fastapi`, com os seis IDs informados pelo agente. O cadastro da API persiste `slug` e `name`; tecnologias e caminhos não foram persistidos. Nenhum ticket, run ou sessão foi criado nesse teste, segundo o relato do agente.

## Atualização — ticket e run no PostgreSQL

No banco `ai_engineering_workspace`, o projeto `webagil` já existia e não havia ticket `EVOLOG-31599` nem a run `2026-11-12-evolog-31599-support`. O arquivo arquivado `state.json` indicava squad `webagil-dev`, pipeline `support` e status `completed`; a pasta continha cinco arquivos. O site Jira `evolog.atlassian.net` foi identificado em documentação local do OpenSquad, sem chamada à API Jira para confirmar o conteúdo do card.

`POST /api/tickets` retornou HTTP 201 e criou o ticket `13de93e6-a823-4ec5-8b18-de84af8c471e`. O comando `workspace:import-opensquad webagil webagil-dev 2026-11-12-evolog-31599-support --ticket=EVOLOG-31599` foi executado duas vezes: ambas retornaram a run `51d64925-2acc-4efc-bb64-396c39de5509` e cinco arquivos encontrados. Em novo processo PowerShell, `history.ps1 -TicketKey EVOLOG-31599` retornou um ticket, uma run, cinco artefatos e um evento. Consulta independente ao PostgreSQL contou exatamente um ticket, uma run, cinco artefatos e um evento. Os cinco hashes SHA-256 e tamanhos registrados coincidiram com os arquivos de origem. Nenhum arquivo OpenSquad foi escrito pelo importador.

## Atualização — catálogo de repositórios e tecnologias

`2026_11_13_000002_add_project_catalog` executou no PostgreSQL (batch 2). Os testes automatizados passaram: 3 testes, 33 asserções, incluindo cadastro, idempotência, caminho Windows inválido e leitura das versões declarada e observada. `sync-project-catalog.ps1` preencheu os seis projetos pela API e foi repetido com as mesmas contagens. Consulta independente ao banco `ai_engineering_workspace` confirmou seis projetos, nove vínculos de repositório e 13 tecnologias; o ticket e a run EVOLOG-31599 permaneceram únicos. Em novos processos PowerShell, `project.ps1` retornou os dois repositórios Webagil e, para fastapi, Python 3.7.4 declarado versus 3.10.8 em `.python-version`. Nenhum repositório de origem foi escrito.

## Atualização — captura de sessões

Na sessão Codex atual, `CODEX_THREAD_ID` foi confirmado como UUID e igual ao `payload.id` do primeiro registro `session_meta` do arquivo local correspondente. Uma run de validação sem ticket (`cab1c214-9ecb-4a4c-b5ae-48c5dad8aa8b`) recebeu essa sessão pelo endpoint HTTP; a repetição retornou o mesmo registro `fa592655-e408-42ca-bc21-68c8b9990b87`. Outro processo PowerShell consultou a run e confirmou uma sessão com método `codex:env+session-meta`. O histórico do ticket EVOLOG-31599 manteve uma run, sem a run de validação. O JSON da tentativa Claude tinha `session_id`, mas indicava erro de autenticação OAuth; o script rejeitou seu registro. `codex exec --json` não iniciou por erro de permissão local, então o método de captura por arquivo JSONL ainda não tem teste funcional. Testes automatizados após a mudança: 3 testes, 40 asserções.

## Atualização — instalação reproduzível

O `composer.json` passou a declarar PHPUnit e Mockery para testes, e o Composer gerou `composer.lock` a partir do Packagist. Uma instalação isolada em pasta nova de `tmp/`, sem o `vendor/` copiado anteriormente, instalou 101 pacotes e executou os scripts de descoberta do Laravel. Nessa cópia limpa, PHPUnit 12.5.44 passou: 3 testes, 40 asserções, PHP 8.5.12. `composer validate --strict --no-check-publish` e `composer check-platform-reqs --lock` também passaram no ambiente local. O script `scripts/windows/install.ps1` agora só gera `APP_KEY` quando ela está vazia e verifica `pdo_pgsql` antes de orientar a migration. O teste de instalação foi feito em uma cópia isolada; a API e o banco existentes não foram reinstalados nem migrados novamente. A validação positiva de Claude Code segue pendente por erro de autenticação OAuth anterior.

## Atualização — ponte Jira MCP

O inventário inicial do terminal mostrou servidores MCP Oracle, mas nenhum Jira. Depois, a configuração somente de leitura do OpenSquad revelou o launcher Jira existente em `tools/mcp/jira.ps1`. O adaptador local iniciou esse servidor isoladamente, confirmou `jira_get_issue` e leu `EVOLOG-31599` com `update_history=false`. O MCP retornou `id`, `key`, `summary`, `status` e `updated`; a data vinha em horário oficial do Brasil e foi convertida com a base de fusos do PHP. `workspace:import-jira-mcp` atualizou o ticket existente `13de93e6-a823-4ec5-8b18-de84af8c471e`; a repetição retornou `unchanged`. A migration `2026_11_13_000003_add_jira_ticket_snapshot` executou no PostgreSQL como batch 3, e as cinco novas colunas foram confirmadas. Em novo processo, a rota de histórico retornou HTTP 200, uma run, cinco artefatos e metadados Jira preenchidos. Testes automatizados: 4 testes, 53 asserções, tanto no `vendor` local quanto na instalação limpa de Laravel 13.42.0. Nenhuma configuração global ou arquivo OpenSquad foi alterado.
