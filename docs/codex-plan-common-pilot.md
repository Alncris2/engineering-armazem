# Piloto LangGraph de planejamento no PowerShell comum

O probe externo read-only executado pelo usuário em PowerShell comum passou com `thread.started`, `turn.completed`, exit 0 e stderr vazio. Os dois pilotos anteriores lançados de dentro do agente terminaram antes de `thread.started` com categoria `permission`; seus recibos e locks `pending` permanecem intactos. Esta etapa prepara **uma única run nova** pelo LangGraph, somente para `plan`, sem modificar variáveis de permissão, ACL, configuração global, OpenSquad, produto ou Jira.

Arquivos sintéticos revisáveis: [tarefa](../config/development/doctor-common-task.txt) e [spec de referência](../config/development/doctor-common-spec.md). A tarefa descreve somente uma função hipotética e critérios de aceite; o executor recebe o texto da tarefa e deve produzir sua própria spec. A spec de referência tem `## Open Questions` com apenas `Nenhuma.` e não é enviada como resultado pronto para o gate. Nenhum dado corporativo ou segredo deve ser acrescentado à tarefa.

Na raiz `C:\htdocs\ai-engineering-workspace`, em **PowerShell comum**:

```powershell
pwsh -NoProfile -File scripts/windows/pilot-codex-plan-common.ps1 -Mode Real -ExecutorTimeoutSeconds 90
```

O script usa o Python da venv e a root CLI `workspace.py`. No `start`, `development.cli` resolve explicitamente o mesmo `codex.cmd` NVM v26.13.1 fixado no probe externo, sem consultar o `codex` do PATH. O processo herda o ambiente normal do PowerShell comum; o script não remove nem altera variáveis `CODEX_*`, proxy ou permissões. Se detectar `CODEX_PERMISSION_PROFILE` ou `CODEX_SANDBOX_NETWORK_DISABLED`, o modo real falha no preflight com `managed_context_detected` antes de criar o marcador ou iniciar Codex. O CLI usa as flags `exec --json --ephemeral --ignore-user-config --sandbox read-only --cd <sandbox exclusivo> --skip-git-repo-check -` e o capturador existente com quota de 2 MiB por fluxo.

Antes da chamada, o script exige a venv, wrapper fixado, tarefa e spec; verifica o gate local da spec, a ausência do marcador persistente `tmp/codex-langgraph-plan.once` e a ausência de diretórios da thread nova. Registra apenas a contagem de processos `codex` visíveis; eles podem pertencer a sessões interativas e a contagem não comprova conflito. O marcador é criado atomicamente antes do `start` e permanece após êxito ou falha. Não execute o script outra vez sem revisar a run; as duas threads antigas nunca são reutilizadas.

O script chama `development start` uma vez e `development status` em **outro processo Python**, sem retomar o agente. Ele imprime um JSON próprio com thread, exit codes, gate `plan`, tentativas, confirmação de checkpoint reaberto, presença do artefato e, se houver falha, somente categoria, exit code, tamanhos, hashes e contagens do diagnóstico. Não imprime plano, prompt, stdout/stderr brutos, valores de ambiente, DSN ou caminhos internos. `status=held_plan_passed` com exit 0 significa plano aprovado pelo gate e estacionado antes de qualquer implementação; `held_gate_failed` ou `inconclusive` retornam exit 1. O gate aprovado não prova implementação, revisão, publicação ou reteste funcional. A categoria `permission`, se reaparecer, não identifica sozinha a causa.

Validação feita no ambiente gerenciado: somente testes com CLI falsa e inspeção de sintaxe PowerShell. A chamada real deste script deve ser feita pelo usuário em PowerShell comum. O agente Shell conectado não foi verificado como terminal comum e não foi usado para executar Codex ou contornar a sandbox.

Para verificar a montagem do script sem banco nem Codex real, use `-Mode Fake`. Ele chama um CLI de teste local, grava um checkpoint **falso** em `tmp/fake-codex-checkpoints` e confirma a leitura em outro processo; o JSON marca `checkpoint_kind=fake_file` e não há plano real. O modo fake usa marcador próprio por thread e não consome o marcador de uso único do modo real.

```powershell
pwsh -NoProfile -File scripts/windows/pilot-codex-plan-common.ps1 -Mode Fake
```
