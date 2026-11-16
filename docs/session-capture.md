# Captura de sessões de executores

O vínculo entre uma run e uma sessão externa só é criado quando um identificador foi obtido da execução real. `POST /api/runs/{id}/sessions` valida UUID, executor e método de captura; repetir o mesmo vínculo retorna o registro existente. O mesmo ID em outra run retorna 409. Uma sessão interna sem ID externo continua permitida, mas não deve ser apresentada como captura comprovada.

## Codex

Dentro de uma sessão Codex que esteja trabalhando na run, execute:

```powershell
pwsh -NoProfile -File scripts/windows/register-executor-session.ps1 -Executor codex -RunId UUID_DA_RUN
```

O script lê `CODEX_THREAD_ID` do processo e exige que o primeiro registro do arquivo de sessão correspondente em `.codex/sessions` seja `session_meta` com o mesmo ID. Esse comportamento foi verificado localmente na CLI 0.167.2; não pressupõe que toda versão ou host do Codex exporte a variável. Se ela não existir ou não corresponder ao arquivo, o script não registra nada. Para execuções não interativas, `-CaptureFile` aceita JSONL de `codex exec --json` apenas quando contém `thread.started` e `turn.completed`; esse caminho está implementado, mas a CLI local não pôde executá-lo neste ambiente devido a erro de permissão ao inicializar seu app-server. A [documentação oficial OpenAI](https://developers.openai.com/blog/eval-skills) confirma que `--json` emite eventos estruturados JSONL.

## Claude Code

Dentro de um subprocesso PowerShell iniciado pela sessão Claude Code:

```powershell
pwsh -NoProfile -File scripts/windows/register-executor-session.ps1 -Executor claude -RunId UUID_DA_RUN -ClaudeFreshOrExplicitResume
```

A [documentação oficial do Claude Code](https://code.claude.com/docs/en/env-vars) informa que `CLAUDE_CODE_SESSION_ID` é definido em subprocessos Bash/PowerShell e atualizado conforme a sessão. Ela alerta que `--continue` ou `--resume` sem ID explícito podem manter o ID de inicialização; nesse caso, não use a captura pelo ambiente para associar a run. O switch `-ClaudeFreshOrExplicitResume` exige que o operador confirme um início novo ou `--resume` com ID explícito. O script aceita também `-CaptureFile` com a saída JSON de `claude -p --output-format json`; exige `type=result`, `subtype=success` e `is_error=false` antes de ler `session_id`. Nesta máquina a tentativa de execução retornou falha de autenticação OAuth; o ID emitido nesse erro foi rejeitado. A captura positiva de Claude Code está pendente de autenticação funcional pelo próprio usuário na CLI.

## Teste realizado

Foi criada uma run de validação sem ticket (`cab1c214-9ecb-4a4c-b5ae-48c5dad8aa8b`, pipeline `workspace-session-capture-validation`). O ID real da sessão Codex atual foi confirmado no seu arquivo `session_meta` e registrado uma vez nessa run. Repetir o script devolveu o mesmo registro. Outra sessão PowerShell consultou `GET /api/runs/{id}` e encontrou o vínculo. O histórico do ticket EVOLOG-31599 permaneceu com apenas a run OpenSquad original. IDs externos não são tokens de autenticação, mas podem identificar conversas privadas; não publique logs ou saídas brutas de executores no repositório.
