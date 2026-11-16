# Contratos de dados propostos (v1)

Todos os IDs internos são UUIDv7 ou UUID aleatório estável; horários UTC ISO 8601; `schema_version=1`. IDs externos sempre com `provider`, `external_id` e escopo de instância. FK e unique constraints no PostgreSQL.

| Entidade | Campos essenciais | Relações/únicos |
|---|---|---|
| Project | id, slug, nome, repos `{path, role, runtime}`, ambientes permitidos, política | slug único; caminhos canônicos Windows, sem segredos |
| Ticket | id, provider=`jira`, site_key, key, summary_redacted, fetched_at | unique(provider,site_key,key); projeto N:N ou 1:N configurável |
| Run | id, project_id, ticket_id?, pipeline_id, pipeline_version, status, environment, instance_path, worktree_path?, branch?, head_sha?, created_at, updated_at, revision | FK Project/Ticket; unique(project_id,client_request_key) |
| ExecutorSession | id, run_id, executor=`claude|codex`, external_session_id?, maestri_terminal_id?, pid?, started_at, ended_at, status | unique(executor,external_session_id) quando conhecido; várias por run |
| Artifact | id, run_id, step, kind, version, path_relative, sha256, size, mime, created_at | unique(run_id,step,kind,version); caminho dentro da raiz autorizada |
| Evidence | id, run_id, artifact_id?, source, source_ref_redacted, observed_at, claim, confidence, sensitivity | prova vinculada a claim; sem payload sensível por padrão |
| Approval | id, run_id, gate, decision, actor_id, decided_at, revision, artifact_hash?, rationale | unique(run_id,gate,revision); aprovação não inferida de saída de agente |
| RunEvent | id, run_id, seq, type, occurred_at, actor, causation_id?, payload_redacted | unique(run_id,seq), unique(run_id,source_event_key) |

Estados `Run`: `created -> validating -> queued -> running -> waiting_approval -> running -> completed`; saídas `failed`, `cancelled`, `needs_reconciliation`. Transição por compare-and-swap em `revision`; `completed/failed/cancelled` terminais salvo operação explícita de reabertura em nova run. `ExecutorSession`: created/running/exited/lost. `Approval`: pending/approved/rejected/expired; apenas decisão humana autenticada avança gate.

Eventos mínimos: `run.created`, `run.validated`, `run.started`, `step.started`, `artifact.recorded`, `evidence.recorded`, `approval.requested`, `approval.decided`, `step.completed`, `run.waiting`, `run.resumed`, `run.failed`, `run.completed`, `executor.started`, `executor.exited`. Payload inclui `run_id`, `seq`, `schema_version`, referência de artefato; não inclui tokens, SQL bruto ou conteúdo de logs por padrão.

Erros tipados: `INVALID_INPUT`, `PROJECT_PATH_MISMATCH`, `PIPELINE_NOT_FOUND`, `PREFLIGHT_FAILED`, `ACTIVE_STATE_CONFLICT`, `ARTIFACT_MISSING`, `GATE_REJECTED`, `EXECUTOR_UNAVAILABLE`, `MCP_UNAVAILABLE`, `APPROVAL_REQUIRED`, `EXTERNAL_STATE_UNKNOWN`, `SECRET_UNAVAILABLE`. Resposta de API: `{code,message,run_id?,retryable,correlation_id}`; mensagem sem segredo.

Idempotência: POST de criação requer `Idempotency-Key` por projeto; repetir retorna a mesma run. Comandos de step usam `(run_id,step,attempt)` único. Eventos recebem sequência monotônica transacional e chave da origem. Repetição de callback não duplica evento/artefato. Hash idêntico e versão igual retorna registro anterior; conteúdo diferente sob mesma chave gera conflito. Escritas externas futuras precisam chave própria e confirmação de estado remoto antes de retry.
