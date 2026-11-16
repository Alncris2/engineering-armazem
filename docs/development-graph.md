# Grafo LangGraph de desenvolvimento

## Executor Codex: planejamento local

**Work e review reais permanecem desabilitados.** A root CLI aceita `--stage plan|work|review`, mas `work` e `review` retornam `CODEX_STAGE_DISABLED` antes de conectar ao PostgreSQL ou iniciar o executor. O grafo também rejeita entrada direta `codex_stage=work|review`. Nenhuma thread de plan held é retomada para avançar a esses estágios.

`services/orchestrator/development/codex_stage_safety.py` prepara verificações locais para a próxima implementação: repo sintético canônico `tmp/development-sandboxes/<thread>/example-repo`, HEAD commitado, árvore limpa, módulo alvo rastreado, rejeição de symlink/junction/hardlink, inventário SHA-256 de todos os arquivos inclusive `.git`, comparação depois da escrita, diff binário e `git diff --check`, congelamento do diff para revisão e lock/recibo pending por `thread:stage:1`. Um validador exige aprovação vinculada a thread, issue, SHA do plano, repo, HEAD, alvo, ator e prazo. **A origem autenticada dessa aprovação, a execução de testes por comando fixo, a proteção comprovada de `.git` durante workspace-write e a invocação Codex work/review ainda faltam.** Os helpers não autorizam nem iniciam work. Testes de crash simulado após escrita, mudança fora do alvo, alteração prévia, falha em `git diff --check` e modificação após congelamento usam Git simulado e não executam Codex real.

O modo `--executor codex` executa **somente `plan`** pelo CLI oficial em um diretório exclusivo sob `tmp/development-sandboxes/<thread>`, com `--sandbox read-only`, `--ephemeral` e `--ignore-user-config`. O restante do grafo continua em modo simulado; `work`, `simplify`, `review`, `fix` e `activate` não são executados pelo Codex nesta integração. Após o gate de `plan`, o grafo para em `held` e só permite `abort` para essa thread. Não declara entrega de código.

Exemplo no PowerShell, na raiz do repositório (um novo `--thread` por tentativa):

```powershell
pwsh -File scripts/windows/workspace.ps1 --json development start --thread meu-plano-1 --issue LOCAL-PLAN-1 --executor codex --task-file config/development/codex-plan-demo.txt
pwsh -File scripts/windows/workspace.ps1 --json development status --thread meu-plano-1
pwsh -File scripts/windows/workspace.ps1 --json development resume --thread meu-plano-1 --decision abort
```

O texto da tarefa é persistido no checkpoint PostgreSQL; não inclua segredos nele. O `thread_id` emitido pelo Codex é capturado apenas se aparecer em `thread.started` junto de `turn.completed`; como a execução usa `--ephemeral`, o recibo marca `session_resumable: false`. Não se presume que o identificador seja retomável. Os recibos de operação são escritos em `tmp/development-runs/<thread>` antes e depois da chamada. Uma queda, timeout, stream incompleto ou lock anterior deixa a operação **inconclusiva**, exigindo reconciliação manual antes de criar outra thread. Isso evita repetir a chamada automaticamente, mas não oferece garantia de execução exatamente uma vez.

Se a invocação falhar, `diagnostic.json` é gravado atomicamente na mesma pasta da run. Ele contém apenas categoria fixa (`invalid_flag`, `auth`, `network_or_proxy`, `permission`, `app_server` ou `unknown`), exit code, tamanhos e SHA-256 dos fluxos, contagens de tipos de evento conhecidos e timestamps. A classificação usa padrões fixos na saída mantida temporariamente em memória e cai em `unknown` quando não há evidência suficiente. O arquivo não guarda stdout/stderr bruto, prompt, texto de evento, variáveis de ambiente, DSN, credenciais nem caminho completo. Recibo `pending` e locks são preservados para reconciliação, sem retry. Um hold Codex por gate `plan` falho devolve código `CODEX_EXEC_INCONCLUSIVE` ou `PLAN_GATE_FAILED` e exit code não zero, com thread/status no JSON da root CLI. O hold deliberado após gate aprovado devolve exit code 0.

Os retries automáticos do grafo ficam restritos à simulação; o modo Codex faz uma tentativa de planejamento. Dois leitores drenam stdout JSONL e stderr em paralelo. Cada fluxo tem quota de 2 MiB em memória; ao ultrapassá-la, o processo é interrompido imediatamente e o recibo continua pendente. Um teste com processo Python local emitindo saída contínua confirmou o término antes do timeout, sem executar o Codex real. O processo tem timeout configurável (máximo de 600 s). No Windows, o timeout tenta encerrar a árvore exata do PID iniciado por `taskkill /T /F`, com esperas limitadas; se esse comando falhar, encerra o processo pai e mantém o recibo pendente. Nessa condição algum descendente pode sobreviver: confirme os processos antes de iniciar outra thread. O recibo local prova apenas o que a CLI registrou nesta máquina; não é prova independente de autoria, revisão ou execução remota.

O gate determinístico de especificação rejeita um plano cujo `## Open Questions` tenha qualquer conteúdo diferente de `Nenhuma.`. O `plan` aprovado pelo gate ainda fica em hold antes de `record_plan` neste modo restrito. Um probe isolado anterior retornou `thread.started`, `turn.completed` e `CODEX_PROBE_OK`; ele não comprova a invocação pelo grafo. O piloto real `doctor-diagnostic-20261113184617-oqu5o2` fez uma única chamada read-only e saiu com código 1, sem eventos em stdout. O diagnóstico registrou categoria `permission` por padrão fixo, 339 bytes de stderr e nenhum texto bruto. A origem específica da permissão não foi comprovada. A run ficou `held` com gate `plan` falho; `workspace.py development status` em processo novo preservou thread/status e retornou código não zero. Recibo pending e locks permanecem para reconciliação; não houve retry, plano produzido ou execução de outros estágios.

Implementação em `services/orchestrator/development/`, baseada na leitura somente leitura dos 151 elementos de `sldc-graph.excalidraw`. Este grafo é independente do workflow de suporte. Não usa OpenSquad, MCP, LangChain como camada de agentes, Claude, Linear ou GitHub. Nesta fase, também não escreve no Jira. `record_plan` grava `workplan.json` no diretório local da run; `activate` conclui apenas um handoff local, sem criar ou mesclar PR.

## Fluxo

`setup → readiness → run_plan → gate_plan → auto_shutdown_after_plan → plan_confidence → record_plan → run_work → gate_work → auto_shutdown_after_work → run_simplify → gate_simplify → auto_shutdown_after_simplify → run_review → gate_review → auto_shutdown_after_review → run_fix → gate_fix → auto_shutdown_after_fix → run_review ... → run_activate → gate_activate → auto_shutdown_after_activate → done`.

Quando `simplify_enabled=false`, o fluxo vai de `auto_shutdown_after_work` diretamente para `run_review`. O `entry_probe` permite iniciar em um estágio escolhido apenas se os recibos locais dos estágios anteriores passarem novamente pelos gates. Erros de setup, entry probe e gravação do plano vão para `fail`. Um hold entra em `await_human`, que usa `interrupt`; a retomada recebe `Command(resume={"decision":"resume"})` ou `{"decision":"abort"}`. A recuperação volta à readiness, execução ou gate salvo no hold. `abort` termina em `aborted`.

Readiness `None` permite planejar; readiness `False` segura a run. Confiança ilegível ou abaixo do limiar padrão de 70 segura a run. Os gates validam estágio e issue, recibo SHA-256 de arquivo confinado ao diretório da run, texto do plano, lista de arquivos alterados, sinais explícitos de checks, IDs e estado dos findings, resolução de todos os findings abertos e ausência deles antes da ativação. Em `evidence_mode=local_git`, estágios após o plano exigem um `git_snapshot` do hook: o gate consulta `git rev-parse` e `git status` em modo somente leitura e compara root, HEAD e arquivos alterados; em work, os arquivos declarados precisam aparecer no status. O CLI de simulação usa `evidence_mode=simulation`. Seus sinais **não comprovam testes de código, revisão humana, estado Git ou PR real**. Hooks reais ainda precisam executar e conferir testes e evidência Jira somente leitura.

O plano deve ser uma spec Markdown baseada em `config/templates/development-spec.md`. `gate_plan` exige a seção `## Open Questions` com apenas `Nenhuma.` ou `None.`; uma pergunta, placeholder ou seção ausente reprova o gate mesmo com confiança acima de 70. A decisão deve ser incorporada ao corpo da spec antes de remover a pergunta. `record_plan` revalida esse gate ao persistir o plano local.

Falha de gate executa novamente o estágio enquanto houver tentativas. Limites: plan/work/simplify/activate 2, review 3, fix 2. A combinação revisão/correção encerra em hold quando não há orçamento para outra correção/revisão. Um gate esgotado pode ser revalidado após reparo humano do mesmo artefato; outra falha o mantém em hold. `holds_enabled=false` leva a `fail`. Um `shutdown_after` estaciona no boundary após gate aprovado e retoma no próximo nó, sem repetir o estágio.

## Execução local simulada

O CLI é `python -m development.cli` no diretório `services/orchestrator`, com a venv `.venv-workspace`. Ele lê `DEVELOPMENT_CHECKPOINT_DSN` do ambiente, usa `PostgresSaver` e cria suas tabelas de checkpoint via `setup()`. Não imprime a DSN. O cenário JSON contém `readiness`, `confidence` e `stages`, onde cada estágio tem uma lista de resultados por tentativa. Exemplo mínimo de formato:

```json
{
  "readiness": true,
  "confidence": 82,
  "stages": {
    "plan": [{"ok": true, "plan_text": "Plano local"}],
    "work": [{"ok": true, "changed_files": ["src/x.py"], "checks_passed": true}],
    "simplify": [{"ok": true, "checks_passed": true}],
    "review": [{"ok": true, "checks_passed": true, "findings": []}],
    "activate": [{"ok": true, "checks_passed": true, "handoff_ready": true}]
  }
}
```

```powershell
Set-Location C:\htdocs\ai-engineering-workspace\services\orchestrator
$env:DEVELOPMENT_CHECKPOINT_DSN = '<DSN local obtida por meio seguro>'
.\.venv-workspace\Scripts\python.exe -m development.cli start --thread demo-1 --issue EVOLOG-123 --scenario C:\caminho\scenario.json --workspace-root C:\htdocs\ai-engineering-workspace
.\.venv-workspace\Scripts\python.exe -m development.cli status --thread demo-1 --scenario C:\caminho\scenario.json
.\.venv-workspace\Scripts\python.exe -m development.cli resume --thread demo-1 --scenario C:\caminho\scenario.json --decision resume
```

Um `--from-stage` aceita `--state-file` JSON com `results` e `attempts` previamente persistidos para o mesmo issue e diretório. O grafo revalida os recibos exigidos; não inventa os artefatos ausentes. Cada executor recebe uma chave estável `thread:stage:attempt`. O simulador não sobrescreve um artefato existente com conteúdo diferente. Um hook futuro com efeito externo deverá aplicar a mesma idempotência do lado do destino. Checkpoint e artefato não formam uma transação única; após queda entre a execução e o checkpoint, a chave e o recibo precisam reconciliar a ação antes de retomá-la.

## Validação e limites

```powershell
Set-Location C:\htdocs\ai-engineering-workspace
services\orchestrator\.venv-workspace\Scripts\python.exe -m unittest discover -s tests\development -v
```

O teste PostgreSQL roda quando `DEVELOPMENT_CHECKPOINT_DSN` está definida; ele fecha a conexão após um hold, abre outra e retoma a mesma thread. Sem DSN, é pulado. Os testes criam pastas únicas sob `tmp/development-tests/` e verificam o caminho resolvido antes da limpeza. A Git CLI local foi exercitada em modo somente leitura; nenhuma CLI de Jira, GitHub, Linear ou Claude foi conectada ou testada funcionalmente. Não há interface própria nem fila/worker de produção. O campo de hold representa a intenção de bloqueio; não altera status nem comenta em Jira. O handoff final representa prontidão segundo evidência simulada, sem publicação externa.
