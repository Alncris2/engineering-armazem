# Mapa completo do AI Engineering Workspace

Mapa iniciado em 14/11/2026. Os Marcos A, B e C preservam fatos históricos; o marco de preparação abaixo registra a leitura de 16/11 e a nova direção solicitada. Resultados históricos não equivalem a uma verificação operacional atual.

## Preparação da migração Maestri → Orca — 2026-11-16

O usuário definiu a migração do Maestri para o Orca como próximo passo. Esta rodada prepara o entendimento: revisou a estrutura, este mapa, resumo, instruções, arquitetura, plano, código e referências de integração; não iniciou a migração. A busca de arquivos encontrou seis diretórios temporários de teste com acesso negado. Arquivos ignorados, segredos, conteúdo completo de terceiros, banco, serviços, notas e estado atual do canvas não foram inventariados integralmente.

**Verificado nesta sessão:** branch `main` sem commit inicial e sem remote listado; `git status` mostrou 132 caminhos não rastreados, incluindo o mapa, código e dois caches PHP Laravel. A contagem é limitada por erros de acesso e não representa inventário de segurança. `.maestri/roles` existe e `.maestri/` é ignorado; seu conteúdo e as notas vivas não foram validados nesta rodada. `orca` não foi reconhecido pelo PowerShell, e `ORCA_CLI_COMMAND` e `ORCA_DEV_REPO_ROOT` estavam ausentes; não foi possível carregar o guia da versão instalada nem validar uma sessão Orca. Isso não prova que o aplicativo não esteja instalado em outro local. Não foram executados testes, consultas ao banco, serviços ou integrações remotas.

**Onde estamos:** o Core Laravel/PostgreSQL, CLI PowerShell/Python, LangGraph e adaptadores são a fundação do produto e a arquitetura já prevê uma CLI comum a Maestri e Orca. Recuperação de histórico e checkpoint foram demonstradas em rodadas anteriores; disponibilidade e conteúdo atuais não foram rechecados. O fluxo de suporte mantém checkpoints e lease para o estado compartilhado OpenSquad; a situação da EVOLOG-33092 no Marco C é histórica. A engenharia interna de desenvolvimento tem `plan` restrito e `work/review` reais bloqueados; simulações e proposta de aprovação não mudam esse limite. A Fase B e seu Portão A permanecem sem aceite registrado.

**Superfícies a transportar ou adaptar na próxima etapa:** (1) instruções e papéis de coordenação, especialmente `instruções.md` e `docs/maestro-workspace-prompt.md` e `docs/maestro-engineering-independent.md`, hoje específicos do Maestri; (2) notas Mapa/Resumo, specs, handoffs, status de andares e referências em `.maestri`, sujeitos a inventário e preservação; (3) terminais, delegação, revisão e isolamento por worktree, a mapear contra capacidades efetivas do Orca; (4) acesso à CLI/Core, Jira, Oracle, Grafana e OpenSquad, com permissões e configuração existentes verificadas sem copiar segredos; (5) sessões, runs, checkpoints, leases e artefatos, cuja continuidade deve ser reconciliada, não presumida pela troca de interface.

**Sequência proposta para a próxima etapa:** localizar e validar o Orca na sessão correta e consultar seu guia; inventariar Maestri e Orca em leitura, incluindo trabalhos ativos e onde vivem os dados; produzir matriz de equivalência e lacunas com destino e critérios de aceite; definir preservação e baseline versionado seguro antes de depender de worktrees; adaptar instruções e realizar piloto isolado, começando pelo suporte, com histórico e gates preservados; somente depois planejar a transição dos demais fluxos. Não apagar Maestri nem alterar estados ativos durante o inventário. O plano depende das capacidades reais do Orca, ainda não verificadas.

O antigo próximo marco C.1/C.2 continua registrado como histórico e pendência de engenharia, mas não é disparado automaticamente: a prioridade atual é preparar a migração. Esta atualização é documental; não confirma migração, continuidade de sessões, publicação ou teste funcional.

## Marco C — retomada da engenharia em 2026-11-15 21:25 -03:00

- A demanda EVOLOG-33092 avançou após o Marco B: Jira GET 200 confirmou id 113480; ticket Core 99430c22-d6c9-4808-8e50-8da41e7f811a foi criado. A auditoria independente posterior registrou run LangGraph 9811befd-19d5-4a90-8209-85ae0d75411e em waiting\_investigation e lease opensquad:webagil-dev dessa run. OpenSquad run 2026-11-15-205800 chegou a waiting, etapa 3/5, com análise produzida e decisão operacional pendente. O status atual do andar Suporte: EVOLOG-33092 no Maestri permanece blocked. Esses dados de run/lease são da auditoria anterior; esta atualização não reconsultou o banco nem o state.json.

- Diagnóstico estático da falha de tickets: GET /api/tickets?key=EVOLOG-33092 teve timeout em prova anterior, enquanto GET /api/projects respondeu 200. A rota chama CoreController::tickets, que consulta tickets com filtro por ticket\_key, ordenação e limite 100, e devolve JSON. Não há causa demonstrada para o timeout. A suíte Feature/CoreTest cobre histórico por UUID, mas não GET filtrado por chave. A CLI resolve a chave via essa listagem antes de buscar o histórico; o timeout prejudica esse caminho. Não houve reprodução HTTP nesta atualização.

- O Maestro Engenharia Independente foi finalizado pelo usuário. A sessão atual do Ground lista somente Codex #3 e as notas Resumo, Mapa do Workspace e Instruções. O prompt independente persiste em docs/[maestro-engineering-independent.md](http://maestro-engineering-independent.md). Esse Maestro deve usar o Maestri e agentes Codex visíveis para desenvolver o Workspace; o próprio Core, LangGraph e OpenSquad são objetos sob teste, não o mecanismo de desenvolvimento.

- Próximo marco: novo Maestro independente define spec concreta, delega reprodução cronometrada e diagnóstico da rota, depois correção mínima e revisão independente; valida ticket e histórico em processo novo sem alterar a run de suporte. Em paralelo, inventaria arquivos/segredos/gerados e lacunas de acesso antes de propor commit inicial. Git main continua sem commit inicial e com arquivos não rastreados (verificado nesta atualização). PG18 Fase B e work/review internos seguem fora desta etapa.

- Os enunciados no Marco B sobre zero runs EVOLOG-33092 e lease da EVOLOG-31599 são históricos, superados pelo registro posterior acima. A decisão operacional do suporte permanece separada da engenharia do Core.

- Marco C.1, diagnóstico C1 entregue por Sonda em 15/11 21:43-21:44 -03: GET /api/projects 200/0,655 s; /api/tickets 200/0,433 s; filtro EVOLOG-33092 200/0,452 s e UUID esperado; history por UUID 200/0,563 s com 1 run. SQL filtrado em transação READ ONLY 1,570 ms; EXPLAIN execution 0,068 ms. API e PG já ativos; log Laravel vazio. O timeout anterior não foi reproduzido; causa permanece INCONCLUSIVA. Sem correção ou prova atual de preservação dos estados da run/lease/checkpoint. Evidência comunicada pelo agente, sem reteste do Maestro.

- Marco C.1, inventário C4 entregue por Crivo: main sem HEAD/remote; 128 não rastreados visíveis, 32.535 ignorados, 35 erros de acesso (6 diretórios tests/development/tmp\* e 29 tmp). .env ignorado, sem leitura de valores. Dois caches Laravel gerados visíveis devem ficar fora do Git; até 126 candidatos condicionais exigem revisão de catálogo e docs com contexto corporativo. Nenhum add/commit/push ou limpeza. Contagens não cobrem caminhos inacessíveis.

- Marco C.1, proposta C6 de Crivo em 16/11 (somente leitura): dos 128 visíveis anteriores, 101 para inclusão condicional, 25 adiados (24 docs e config/projects/catalog.json) por conteúdo corporativo, 2 caches Laravel gerados para exclusão. Propôs /apps/control-api/bootstrap/cache/\*.php no .gitignore, pois a regra atual na raiz não cobre os caches. Sem edição, stage ou commit; 35 erros de acesso e revisão final de segredos/conteúdo ainda limitam o baseline. Recontar após C5.

- Marco C.1, C5 entregue por Sonda e aprovado por Crivo em 16/11: novo apps/control-api/tests/Feature/TicketFilterTest.php (67 linhas), 2 testes/25 asserções em SQLite :memory:, exit 0 na revisão independente (955 ms). Cobre chave exata, parcial, listagem sem filtro, envelope data/error e ordenação. Não altera controller; não reproduz latência/causa do timeout histórico em PostgreSQL. Plano de observação aprovado como proposta: gatilho 5 s, até 4 HTTP e SQL READ ONLY limitados, logs sanitizados e comparação segura dos estados se alegar preservação; não executado. Estados do suporte não reconsultados nesta rodada. Baseline permanece proposta sem stage/commit; recontar após novo teste.

- Marco C.1, revisão independente adaptada por Crivo: GET filtrado 200 em 1,283 s (curl, timeout 5 s), CLI history da chave em novo processo exit 0, ticket UUID esperado e 1 run waiting\_investigation; GET history direto 200 com 3 eventos. Leituras SQL READ ONLY antes/depois mantiveram run 9811befd-19d5-4a90-8209-85ae0d75411e, lease opensquad:webagil-dev da mesma run e checkpoint 1f1e14fb-b331-6e98-8003-44cf6b783f08 idênticos. PHPUnit não rodado por RefreshDatabase/migrations; falta teste específico do filtro. Sem diff/C2, pois o timeout histórico segue sem causa. Marco C.1 PARCIAL; não iniciar C.2 automaticamente.

## Marco B — atualização operacional em 2026-11-15 13:41:26 -03:00

DEMONSTRADO: GET Jira EVOLOG-33092 pelo adaptador direto (id 113480); ticket Core 99430c22-d6c9-4808-8e50-8da41e7f811a importado e conferido; script Oracle WebÁgil PRD realizou somente preflight SELECT em transação read-only e retornou ORCL/ROOT; baixar-jira salvou XML e um anexo em C:\\htdocs\\Demandas\\EVOLOG-33092; worktree webagil-back criado de origin/dev, HEAD c1860a0ab, branch EVOLOG-33092 com upstream origin/EVOLOG-33092. Maestro Workspace no Ground com papel global, preset Codex Maestro Workspace e instruções reutilizáveis; papéis locais específicos do 33092 removidos. NÃO DEMONSTRADO: SELECT do atendimento 2077039, Grafana remoto, abertura SSH, execução OpenSquad 33092, run LangGraph 33092, work/review real.

BLOQUEIO verificado naquele momento (superado pelo Marco C): zero runs Core vinculadas ao 33092; lease opensquad:webagil-dev ainda pertence à run b4512878-7f03-49b4-8160-bc298e852912 (EVOLOG-31599) em waiting_approval; state.json OpenSquad support está waiting etapa 3/5. O workflow LangGraph foi mantido e, por desenho, aguarda investigação supervisionada em vez de iniciar OpenSquad. Nenhum lease, checkpoint, gate ou estado OpenSquad foi alterado. Verificação HTTP adicional em 15/11: GET /api/projects respondeu 200 com 6 projetos; GET /api/tickets?key=EVOLOG-33092 atingiu timeout de 5 segundos antes de status HTTP. A API responde em parte, mas a rota de tickets permanece sem validação funcional. O Marco A abaixo permanece histórico e seus enunciados sobre integração Oracle/Jira devem ser lidos à luz deste Marco B.

## Marco A — validação operacional em 14/11/2026

DEMONSTRADO nesta rodada: PostgreSQL 18.7 respondeu; migrations 000001–000004 aplicadas e 000005 pendente; seis projetos consultados; API Laravel GET respondeu em loopback durante servidor temporário; CLI tickets history recuperou EVOLOG-31599 em dois processos independentes (PIDs 22588 e 24248), com duas runs e cinco artefatos da run OpenSquad. A API temporária foi encerrada; porta 8088 sem listener ao final. O checkpoint LangGraph da run waiting_approval foi lido em dois outros processos (PIDs 1288 e 39616), mesmo checkpoint_id, sem /resume. Cinco arquivos OpenSquad existem e os SHA-256 recalculados coincidem com o banco. Jira REST GET confirmou identidade/resumo/status, mas updated remoto 15:03:09-03 é posterior ao snapshot local 09:58:14-03; conteúdo remoto adicional não foi lido. Nenhuma migration, DDL, sync, import, work/review, Jira write ou alteração OpenSquad. Commit inicial NÃO aprovado nesta revisão: 116 candidatos visíveis, seis diretórios de teste inacessíveis, cache Laravel gerado candidato e catálogo corporativo a revisar. Recibos pending preservados. Marco A atende critério de recuperação de chamado real em novo processo, com referências verificáveis; não comprova retomada de sessão LLM, reteste QAS nem execução da run waiting_approval.

## 1. Leitura rápida

O Workspace Core local tem código de API Laravel, persistência PostgreSQL, CLI para PowerShell, modelo de tickets/runs/artefatos e importação OpenSquad somente leitura. Essas partes foram usadas em validações históricas de 13/11; a disponibilidade atual do serviço e do banco não foi revalidada nesta atualização. Há grafos LangGraph para suporte supervisionado e desenvolvimento. Um piloto de Codex plan read-only foi bem-sucedido segundo o relato do usuário e artefatos locais históricos, com checkpoint PostgreSQL reaberto em outro processo naquele teste; ele não foi reexecutado nesta auditoria. Work e review reais continuam desabilitados no código.

O esforço histórico de Fase B entrou na segurança da futura execução de código: aprovação humana, WebAuthn, serviço Windows, papéis separados no PostgreSQL e ensaios PG18. Esse conjunto é sobretudo desenho e simulação. O Portão A de PostgreSQL não passou. Nenhum DDL da Fase B foi aplicado ao banco pessoal. A revisão da última prova offline de SQL foi pausada por solicitação do usuário.

**Legenda usada abaixo:** IMPLEMENTADO = código presente; DEMONSTRADO = execução ou teste específico registrado; SIMULADO = fake/mock sem serviço real; DESENHO = documentação/proposta; BLOQUEADO = execução real recusada pelo código ou sem pré-condições. Um teste histórico não garante que serviço e dados continuam iguais hoje.

## 2. Objetivo inicial e mudanças de direção

### Briefing inicial: Fase 1 — Fundação

Criar, em Windows nativo e sem frontend próprio, um Workspace Core pessoal que persistisse projetos, tickets Jira, runs, sessões de executores, artefatos, evidências, decisões e histórico. O plano incluía API Laravel, PostgreSQL/pgvector, adaptador OpenSquad somente leitura, interface CLI ou MCP para agentes e testes de migrations, importação e consulta do histórico em sessão nova. O OpenSquad original deveria permanecer intacto.

### Decisões posteriores do usuário

- Maestri e Orca devem consumir o mesmo Core por CLI, sem lógica presa à interface.

- LangGraph é o motor direto de orquestração; não usar LangChain como camada de agentes.

- Preferir PowerShell, Python, CLIs e APIs oficiais; o fluxo novo não depende de MCP.

- PostgreSQL é memória persistente; RAG semântico fica opcional e fora do caminho crítico.

- Claude pode esperar; começar pelo Codex. O próprio Codex deve fazer tarefas de implementação via Maestri, com coordenação e revisão independentes.

- Nunca executar work/review real sem controles, testes e aprovação humana adequada.

### Consequência prática

O projeto passou de um Core de histórico para um objetivo adicional muito maior: um executor de desenvolvimento supervisionado. A Fase B recente estuda a fronteira de segurança desse executor. Ela não é requisito para consultar tickets e importar runs, que já são o valor central da primeira fase.

## 3. Estrutura criada no checkout

| Área | O que contém | Estado |

| --- | --- | --- |

| apps/control-api | Laravel 13, rotas HTTP, migrations, comandos Artisan e testes | Implementado; funções centrais testadas historicamente |

| services/orchestrator | LangGraph de suporte, grafo de desenvolvimento, hooks Codex plan, checkpoint PostgreSQL | Suporte supervisionado e desenvolvimento simulado; plan Codex real pilotado |

| services/knowledge | Cliente de histórico da API local | Leitura implementada; RAG vetorial pendente |

| adapters/opensquad | Importação arquivada e gate de spec preparado | Importação read-only demonstrada; gate externo não aplicado |

| adapters/jira | REST GET atual e ponte MCP histórica | Snapshot local demonstrado; sem escrita Jira no fluxo atual |

| adapters/oracle, adapters/grafana | Scripts de consulta somente leitura | Código presente; sem teste remoto funcional registrado |

| adapters/git, adapters/executors | Inspeção local Git e probes de versão de CLIs | Utilitários locais; não são execução de pipeline |

| config/projects, config/development, config/templates | Catálogo, cenários de simulação e template de spec | Implementado como configuração/entrada |

| scripts/windows | Instalação, API, CLI, histórico, catálogo e probes/pilotos | Scripts presentes; provas variam por script |

| docs, tests | Arquitetura, validações, riscos, Fase B e testes | Misturam resultados históricos e propostas futuras |

O checkout atual está em main, sem commit inicial e sem remote configurado. Os arquivos do projeto aparecem como não rastreados. Há .env local, vendor, venv e tmp ignorados; a auditoria não leu credenciais. Essa ausência de HEAD versionado é uma pendência concreta de preservação e revisão do trabalho.

### Dependências e versões registradas

O composer.json da API exige PHP ^8.3 e Laravel ^13.8; o lock observado nesta auditoria contém Laravel 13.42.0, PHPUnit 12.5.44 e Mockery 1.6.15. O pyproject.toml do orquestrador exige Python &gt;=3.13; o uv.lock observado contém LangGraph 1.2.21, langgraph-checkpoint-postgres 3.2.0, psycopg 3.3.9 e oracledb 3.4.2 como extra opcional. PostgreSQL 18.7 e pgvector 0.8.7 foram observados em etapas históricas. Esses locks e observações não são um teste novo da versão servida hoje por cada processo.

## 4. Matriz do briefing inicial de seis etapas

| Etapa original | O que foi feito | Evidência e limite | Estado |

| --- | --- | --- | --- |

| 1. Discovery | Inventário Windows, runtimes, PostgreSQL/pgvector e leitura do OpenSquad; docs de arquitetura, ambiente e riscos | Descoberta documentada. OpenSquad tem state.json ativo por squad e outputs por run; execução concorrente exige isolamento. Algumas versões e capacidades precisam ser rechecadas quando usadas. | Concluída como descoberta histórica |

| 2. Fundação do monorepo | Estrutura apps/services/adapters/config/scripts/docs, Laravel, Python e wrappers PowerShell | Código e arquivos presentes. Sem frontend próprio e sem WSL. | Implementada |

| 3. Persistência Core | Migration 000001 cria nove tabelas com UUID, FKs, índices e unicidade; 000002 catálogo; 000003 snapshot Jira; 000004 leases | Migrations 000001–000003 foram executadas no PostgreSQL conforme validação histórica. A execução atual de 000004 não foi reconfirmada nesta auditoria. Documento data-model contém campos futuros que não estão integralmente no schema. | Core implementado; estado atual do DB não reconsultado |

| 4. API local | Projetos, repositórios, tecnologias, tickets, histórico, runs, sessões, artefatos, evidências e busca textual | Rotas e controller presentes; testes PHPUnit e chamadas HTTP históricas. API usa loopback e não tem autenticação multiusuário, conforme escopo pessoal. | Implementada e historicamente testada |

| 5. Adaptador OpenSquad | Leitura de state.json/artefatos arquivados, validação de paths/formato, importação transacional e idempotente | EVOLOG-31599 foi importado historicamente duas vezes com mesmo UUID e cinco artefatos. Não inicia nem retoma pipeline, não altera origem. | Importação read-only demonstrada |

| 6. Interface para agentes | [workspace.py](http://workspace.py), wrapper PowerShell, history.ps1 e cliente knowledge | Histórico pode ser consultado por CLI/API; sessão nova foi usada em validações históricas. Registro específico em Orca não foi testado. | CLI implementada; Orca pendente |

### Critérios de aceite originais

- Windows sem WSL2 e sem frontend: atendido na arquitetura e nos scripts.

- PostgreSQL conectado, migrations Core e testes: demonstrados historicamente para o Core; requer rechecagem operacional atual antes de afirmar serviço ativo.

- Run OpenSquad existente importável: demonstrado historicamente com EVOLOG-31599.

- Histórico consultável em nova sessão: demonstrado para Core/plan checkpoint em testes históricos, com alcance restrito aos dados importados.

- OpenSquad original preservado: os fluxos usados foram de leitura; o spec-gate preparado não foi aplicado na origem.

- Nenhuma credencial exposta: os relatos e esta auditoria não abriram .env ou valores secretos; isso não substitui uma varredura formal antes de versionar/publicar.

- IDs Claude/Codex não inventados: captura de sessão só quando houve fonte observável; Claude positivo segue pendente.

### Plano interno ordenado de dez tarefas, criado na descoberta

docs/[implementation-plan.md](http://implementation-plan.md) detalhou dez tarefas dependentes. Esse documento é um plano mais amplo que o briefing de seis etapas acima. Parte de seus requisitos foi alterada por decisões posteriores: por exemplo, o desenho atual prefere CLI sem MCP, não inclui dashboard próprio nem autenticação multiusuário. A tabela preserva o alvo histórico e mostra o quanto foi efetivamente alcançado.

| Tarefa do plano interno | Resultado observado | Aceite original ainda pendente |

| --- | --- | --- |

| 1. Resolver ambiente base | Windows, Python, PostgreSQL/pgvector e ferramentas inventariados historicamente | Revalidar versões/runtime quando necessário; gerenciador de serviço Windows não implantado |

| 2. Provar Maestri local | CLI e colaboração no canvas usadas; agentes conectados nesta fase | Presets Claude/Codex, múltiplos terminais e dashboard não foram comprovados conforme todo o aceite antigo; dashboard próprio foi descartado |

| 3. Banco e migrações de controle | Nove tabelas Core e migrations de catálogo/Jira; testes históricos | Outbox, todas as transições e migração reversível testada conforme o plano completo não demonstradas |

| 4. API Laravel de controle | API local de projetos/tickets/runs/histórico implementada | OpenAPI, RBAC, approvals e teste de acesso negado do plano antigo não entregues; multiusuário ficou fora do escopo atual |

| 5. Worker LangGraph mínimo | Grafos e checkpointer PostgreSQL; retomada em cenários de teste | Fila/outbox, health, reconciliação completa e prova de restart sem duplicação em todos os estágios não concluídas |

| 6. Adaptador OpenSquad isolado | Importador somente leitura e preflight; lease para state.json compartilhado | Instância por run com execução real, dois runs simultâneos e gates preservados em execução não demonstrados |

| 7. Executores Claude/Codex | Captura observável e piloto Codex plan-only; recibos/locks para plano | Claude funcional, work/review, retomada de sessão e recuperação de processo órfão ainda pendentes |

| 8. MCPs leitura/Jira | Ponte MCP histórica e Jira REST GET atual; adaptadores Oracle/Grafana de leitura em código | Fluxo remoto completo Jira/log/Oracle com auditoria e falha tipada não testado; decisão atual elimina dependência MCP |

| 9. RAG controlado | Busca textual local e pgvector disponível historicamente | Ingestão, embeddings, citações, política de fontes e isolamento entre projetos não implementados |

| 10. Operação Windows | Scripts de desenvolvimento/execução local | Serviço, reboot, backup/restore, logs rotativos e rotação de credenciais não ensaiados |

## 5. Core Laravel e persistência, com precisão

### API e modelo

routes/api.php contém 16 declarações de rota. CoreController usa DB facade/query builder diretamente, sem modelos Eloquent em app/Models. A API devolve envelope JSON com data/error e valida entradas; cria identificadores UUID e usa chaves/constraints para idempotência.

Operações presentes: listar/criar/consultar/editar projetos; listar/criar repositórios e cadastrar tecnologias; listar/criar tickets; consultar histórico completo de ticket; criar/consultar runs; anexar sessões, artefatos e evidências; buscar memória textual. O histórico agrega runs, executor_sessions, artifacts, evidence, decisions e run_events. A busca atual usa LIKE em resumo/chave de tickets e alegações de evidência, com limite; não é busca semântica.

### Migrations

| Arquivo | Conteúdo | Limite de prova |

| --- | --- | --- |

| 000001_create_workspace_core.php | projects, repositories, tickets, runs, executor_sessions, artifacts, evidence, decisions e run_events | Executada no PG em validação histórica |

| 000002_add_project_catalog.php | Descrição de projeto, path único por projeto, tecnologias/versionamento/fonte | Executada em validação histórica |

| 000003_add_jira_ticket_snapshot.php | Campos de snapshot Jira no ticket | Executada em validação histórica |

| 000004_create_workflow_leases.php | Lease único por recurso e vínculo à run | Código presente; estado atual da migration não reconsultado |

| 000005_create_work_approval_contract.php | Credentials, challenges, approvals e 11 CHECK de aprovação | Testada apenas em SQLite :memory: na Fase A; NÃO aplicada ao PG pessoal |

O documento docs/[data-model.md](http://data-model.md) descreve um contrato mais ambicioso, como revisões/CAS, RBAC e outros controles. Não se deve interpretar o documento como inventário fiel de colunas já criadas.

### Dados de projetos e ticket demonstrados

Os seis projetos cadastrados foram Webagil, Server, Warehouse, LMS, Agend Node e fastapi. O cadastro inicial gravou somente nome/slug; tecnologias e paths não estavam nesse primeiro POST. Uma validação posterior do catálogo registrou historicamente seis projetos, nove repositórios e treze tecnologias. Não reconfirmei essas contagens no banco agora.

O histórico local de EVOLOG-31599 teve, em consulta histórica, uma run OpenSquad concluída, cinco artefatos e um evento run.imported; não havia sessões, evidências estruturadas ou decisões naquela consulta. Isso é o recorte do Workspace Core, não um inventário do Jira nem de todas as pastas OpenSquad.

## 6. CLI e operação local

[workspace.py](http://workspace.py) é a entrada principal; scripts/windows/workspace.ps1 é o wrapper PowerShell. A CLI usa API HTTP em 127.0.0.1:8088 por padrão, recusa URL fora de loopback, oferece JSON opcional e erros estruturados. Grupos presentes: projects, repositories, tickets (list/history/add/sync), runs (show/add), sessions add, memory (search/add), opensquad import, pipelines (start/status/resume) e development (start/status/resume).

scripts/windows/start-api.ps1 inicia artisan serve em loopback de forma interativa; não há serviço Windows de produção. history.ps1 consulta a história por ticket key ou ID. project.ps1 e sync-project-catalog.ps1 são clientes do catálogo. install.ps1 prepara dependências e chave da aplicação quando vazia. Probes e pilotos Codex usam marcadores one-shot e saída sanitizada; eles não entregam código.

A CLI é independente de Maestri no código. PowerShell comum e Maestri foram exercitados em contextos específicos. Orca está previsto quando instalado/configurado, mas não há teste funcional registrado; não chamar compatibilidade Orca de concluída.

## 7. OpenSquad, Jira e outros adaptadores

### OpenSquad

ImportOpenSquad.php lê runs arquivadas em squads/&lt;squad&gt;/output/&lt;run&gt;, valida identidade, caminhos, tamanho e links, calcula hashes de artefatos e grava metadados/eventos em transação. Reimportar a mesma run não deve duplicar registros. Não há API de execução OpenSquad comprovada, nem execução/retomada de pipelines pelo adaptador.

adapters/opensquad/spec-gate.mjs e scripts/windows/apply-opensquad-spec-gate.ps1 foram preparados para uma política de spec, mas NÃO aplicados em C:\\htdocs\\squad-ia. O OpenSquad original permanece fora das alterações desta fase. O state.json compartilhado é a razão para o controle de lease e para não presumir concorrência segura.

### Jira

O caminho novo da root CLI usa adapters/jira/get-issue.ps1 com REST GET e importa snapshot validado por comando Artisan. O importador compara identidade do site/ticket e evita repetição. Há uma ponte Jira MCP histórica em adapters/jira/mcp\_[client.py](http://client.py) e docs/[jira-mcp.md](http://jira-mcp.md); ela não é dependência do fluxo CLI atual. Uma leitura/importação Jira foi testada historicamente, mas esta auditoria não chamou Jira. O fluxo atual não comenta nem altera tickets remotamente.

### Oracle, Grafana, Git e executores

Oracle tem script Python limitado a SELECT/WITH e transação READ ONLY; Grafana/Loki usa HTTP GET com limites; Git lê root, HEAD, branch e estado; probes de Claude/Codex/Orca consultam versões. Presença de script não comprova credencial, rede, permissão ou resultado remoto. Oracle teve preflight remoto somente leitura descrito no Marco B, sem SELECT do atendimento 2077039; Grafana e Orca não têm teste funcional remoto registrado para este Workspace. Não há publicação de PR, CI/deploy ou worker permanente.

## 8. LangGraph: o que os dois fluxos realmente fazem

### Suporte supervisionado

services/orchestrator/[workflow.py](http://workflow.py) constrói StateGraph: identificar ticket, recuperar contexto, preparar preflight OpenSquad somente leitura, interromper para investigação, interromper para aprovação humana, validar estado/artefato arquivado e persistir. Usa PostgresSaver para checkpoint e lease de workflow para proteger o state.json compartilhado. Uma run histórica foi descrita como waiting_approval; isso não é resolução automática do ticket. A aprovação por CLI ainda não autentica a pessoa. O código chama PostgresSaver.setup() em runtime, ponto a rever quando houver roles separados.

### Desenvolvimento e Codex

services/orchestrator/development/[graph.py](http://graph.py) modela plan, work, simplify, review, fix e activate, com readiness, confiança, spec gate, record_plan, limites de tentativa, hold/interrupt, recovery e abort. ScenarioHooks e InMemorySaver permitem testar a lógica. Esses estados simulados não são entrega de código.

O adaptador real development/codex\_[cli.py](http://cli.py) aceita somente plan read-only. Usa wrapper Codex NVM fixado, sandbox exclusivo, JSONL, lock e recibo pending/completed, operation_key, timeout e quota de 2 MiB por fluxo. Diagnósticos de falha são sanitizados; falha/crash não dispara retry automático e exige reconciliação manual. O recibo local prova consistência observada, não autoria criptográfica. Depois do plano, a thread fica held e só permite abort no modo Codex. Root CLI e grafo devolvem CODEX_STAGE_DISABLED para work/review reais.

Um piloto REAL em PowerShell comum, relatado pelo usuário, terminou held_plan_passed em uma tentativa para tarefa sintética doctor: plano presente e checkpoint PostgreSQL reaberto em outro processo. Revisão local confirmou hash/recibo/spec sem Open Questions. Não houve work, review, teste de produto, PR, alteração Jira ou OpenSquad. Dois pilotos anteriores terminaram inconclusivos por categoria permission antes de thread.started; locks/receipts pending foram preservados, sem retry.

development/codex_stage\_[safety.py](http://safety.py) tem helpers de baseline Git, diff, escopo e binding para work/review futuros. Isso NÃO habilita os estágios reais, nem substitui snapshot protegido, testes fixos do orquestrador e revisão do diff em invocação separada.

## 9. Memória, RAG e captura de sessões

services/knowledge/[history.py](http://history.py) consulta o histórico da API local. A rota /memory/search usa busca textual. pgvector foi disponibilizado/observado em etapas anteriores, mas não há pipeline de embeddings, chunks, classificação de sensibilidade, indexador ou recuperação semântica operacional. RAG continua opcional e fora do caminho crítico.

scripts/windows/register-executor-session.ps1 e docs/[session-capture.md](http://session-capture.md) tratam captura de identificadores observáveis. Houve validação histórica de uma forma de captura Codex por metadados locais; codex:exec-json isolado não deve ser anunciado como retomada de sessão. Claude Code ainda não teve captura positiva equivalente. Nunca gerar IDs fictícios para preencher executor_sessions.

## 10. Aprovação humana para work: Fases A/B e Portões

### Fase A — contrato e simulação

approval\_[contract.py](http://contract.py) valida payload com thread, issue, hashes de plan/spec, repo/HEAD/inventário/escopo, nonce e prazo. approval\_[mock.py](http://mock.py) usa SQLite e prova mock pública/falsificável; marca usable_for_real_work=false. Testes cobrem troca de campos, replay, concorrência e expiração. O mock não está conectado à retomada real do LangGraph. A migration 000005 existe em código; o teste de migration foi SQLite em memória, não PG pessoal.

### Fase B — desenho, sem implantação

docs/[work-approval-phase-b-design.md](http://work-approval-phase-b-design.md) e docs/[work-approval-phase-b-sql.md](http://work-approval-phase-b-sql.md) propõem serviço Windows sob identidade distinta, cliente interativo WebAuthn, broker/verificador, named pipe autenticado com ACL/SID, snapshot protegido do repo, evidência assinada, quatro DSNs runtime separados mais migrator offline, grants mínimos, claims transacionais e checkpoints sem DDL em runtime. Nenhum desses serviços, roles, ACLs, pipes ou credenciais WebAuthn foi implantado/testado. A API webauthn.dll presente no Windows não comprova autenticador cadastrado nem cerimônia funcional. Hoje a conexão da aplicação é superusuária; ela não é fronteira de segurança contra agente com o mesmo acesso.

### Portão A — PG18 descartável

O ensaio pretendido era provar migration/delta, catálogo, constraints, grants com logins reais, clean/upgrade e restore em outra instância descartável. Tentativa de cluster temporário PG18 falhou no initdb por token restrito Windows antes de SQL. A tentativa seguinte parou no preflight de ACL do floor. Nada foi aplicado. No cluster pessoal, três DBs existentes concedem PUBLIC CONNECT e um PUBLIC TEMP; roles novas seriam globais e não ficariam isoladas apenas por grants em DBs novos. O plano de dois DBs/sete roles ficou NO-GO; uma role migradora adicional elevaria o escopo global para oito roles. O usuário autorizou usar o PostgreSQL pessoal em princípio, mas ainda não aprovou CREATE ROLE/CREATE DATABASE/alterações globais concretas, e faltam guardas executáveis.

Um plano alternativo limitado propõe somente sintaxe/catálogo em um DB novo, zero roles, sem executar a migration Laravel. O documento [pg18-partial-syntax-catalog-plan.md](http://pg18-partial-syntax-catalog-plan.md) fica no floor. Codex #2 criou prova OFFLINE da tradução: 17 statements gerados pelo grammar Laravel espelhado + 11 CHECK literais, transformação determinística para public. e 10 statements do primeiro bloco do delta. Testes locais relatados passaram; Vigia confirmou hashes e estrutura inicial, mas a revisão foi pausada antes de executar verify/self-test e antes de fechar a análise do carregamento Laravel. Isso não é teste PostgreSQL. Ainda faltam fingerprint v1 aprovado, runner PDO com guard antes de cada DDL e revisão/autorização específica de CREATE. O Gate A completo continua BLOQUEADO.

### Portões B e C

Portão B seria serviço/broker/WebAuthn/Windows/PG separados e testados ponta a ponta em isolamento. Portão C seria work real em repo sintético após aprovação humana vinculada. Ambos permanecem NO-GO. Review real também requer contrato próprio e testes independentes.

## 11. Testes e demonstrações: quando e o que provam

| Evidência | Resultado registrado | O que NÃO prova |

| --- | --- | --- |

| Core Laravel em 13/11 | Migrations 000001–000003, chamadas HTTP, importação idempotente de EVOLOG-31599; 4 PHPUnit com 53 asserções em ponto anterior | Serviço/API ativos agora; todas as tabelas/colunas propostas; Jira inteiro |

| Catálogo em 13/11 | Seis projetos, depois nove repos e treze tecnologias na validação histórica | Persistência de tecnologias/paths no POST inicial de projetos |

| Suíte Fase A posterior | 8 testes Python raiz; 53 development (51 executados, 2 skipped sem DSN); 4 PHPUnit/56 asserções em SQLite | WebAuthn, PG real da migration 000005, work/review real |

| Desenvolvimento com DSN | Teste de checkpoint PG condicional; em rodadas registradas houve retomada após nova conexão | Autoridade humana ou execução de código exatamente uma vez |

| Codex plan em PowerShell comum | Uma tentativa real sintética com gate plan aprovado, artefato e checkpoint reaberto | Implementação do doctor, work, review, PR ou deploy |

| Probes anteriores | Falhas permission/inconclusivas preservadas com pending; probe externo read-only passou em PowerShell comum | Causa raiz da permissão ou sucesso dentro do ambiente gerenciado |

| SQL parcial offline | Parser/geração relatados: 17+11 base e 10 delta; cinco mutações rejeitadas | Sintaxe PG18, catálogo, grants, migration Laravel ou isolamento |

Nenhuma suíte foi rodada para produzir esta atualização do mapa. Datas, contagens e resultados acima vêm dos relatórios históricos e da leitura de código/documentação em 14/11.

## 12. Lacunas e riscos que importam agora

1. O Core precisa de reteste curto no fluxo real de trabalho: ticket Jira -&gt; snapshot -&gt; histórico -&gt; run/evidência -&gt; consulta em nova sessão. Validar contra fonte atual, sem presumir que dados de 13/11 continuam iguais.

2. Checkout sem commit inicial/remote: ainda não há baseline versionado para preservar e revisar o monorepo.

3. Acesso PG atual da aplicação é superusuário; segurança de aprovação e separação de checkpoint ainda são propostas. O runtime ainda chama PostgresSaver.setup().

4. Orca, Oracle/Grafana remotos, Claude Code e RAG semântico não foram demonstrados como integrações ponta a ponta.

5. OpenSquad read-only import funciona historicamente; execução/retomada e concorrência independente continuam fora de escopo. Não aplicar spec-gate preparado ao diretório original sem nova decisão.

6. Work/review reais não têm aprovação protegida, snapshot imutável, runner/testes fixos e evidência auditável suficientes. O bloqueio no código é intencional.

7. O floor PG18 contém artefatos de tentativas inconclusivas; não limpar, reutilizar ou fazer rollback automático. Não rodar DDL no banco pessoal a partir de plano ou mock.

## 13. Próximos passos recomendados após a pausa

**Primeiro, estabilizar o caminho diário com EVOLOG-33092:** reproduzir e diagnosticar o timeout do GET filtrado de tickets com limite de tempo e observabilidade; corrigir apenas a causa demonstrada; validar tickets e histórico em novo processo. Reusar o Jira e o ticket Core já confirmados, sem reiniciar a investigação de suporte nem tocar na run ou no lease.

**Depois, preservar a base:** preparar inventário de segredos, arquivos gerados, diretórios inacessíveis e estado Git para revisão do primeiro commit; documentar comandos Windows e retestar o Core. Fazer commit apenas após revisão humana. Validar Orca separadamente quando houver instalação/configuração demonstrada.

**Só se a prioridade for execução de código por agente:** retomar a revisão offline da tradução SQL; preparar fingerprint/runner e ensaio PG18 realmente isolado; implementar serviço de aprovação e papéis/DSNs separados; depois hooks work/review com fake executor, snapshot e gates. Um piloto real de escrita vem por último, em repo sintético e com autorização humana vinculada.

## 14. Onde conferir

- Arquitetura vigente e limites: docs/[architecture-v2.md](http://architecture-v2.md), docs/[development-graph.md](http://development-graph.md), docs/[work-approval-phase-a.md](http://work-approval-phase-a.md), docs/[work-approval-phase-b-design.md](http://work-approval-phase-b-design.md), docs/[work-approval-phase-b-sql.md](http://work-approval-phase-b-sql.md).

- Modelo e Core: apps/control-api/routes/api.php, apps/control-api/app/Http/Controllers/CoreController.php, apps/control-api/database/migrations, docs/[validation-core-v1.md](http://validation-core-v1.md).

- CLI/fluxos: [workspace.py](http://workspace.py), scripts/windows/workspace.ps1, services/orchestrator/[workflow.py](http://workflow.py), services/orchestrator/development, services/knowledge/[history.py](http://history.py).

- Integrações: adapters/opensquad, adapters/jira, adapters/oracle, adapters/grafana, docs/[session-capture.md](http://session-capture.md), docs/[spec-policy.md](http://spec-policy.md).

- Ensaio PG18 parcial: floor Maestri Ensaio PG18 Fase B; documentação offline no arquivo [pg18-partial-syntax-catalog-plan.md](http://pg18-partial-syntax-catalog-plan.md). O floor continua bloqueado para SQL.

**Estado nesta atualização:** Jira e ticket Core EVOLOG-33092 foram confirmados em rodada anterior e há run de suporte no checkpoint humano; a consulta HTTP de tickets por chave ainda tem timeout sem causa demonstrada. O próximo trabalho do Maestro independente é diagnosticar e estabilizar esse caminho, validar o histórico em novo processo e preparar o inventário pré-commit. Work/review internos e PG18 Fase B continuam fora do escopo.
