# Probe externo do Codex CLI

Execute **uma vez**, em um PowerShell comum fora da sandbox do agente, após revisar que não existe um marcador anterior de probe real. O script usa o mesmo `codex.cmd` do NVM e as flags do adaptador, um sandbox novo e vazio sob `tmp`, prompt sintético, captura em memória de até 2 MiB por fluxo e timeout de 12 segundos. Não usa LangGraph nem as duas threads pendentes.

Na raiz `C:\htdocs\ai-engineering-workspace`:

```powershell
pwsh -NoProfile -File scripts/windows/probe-codex-context.ps1 -Mode Real -TimeoutSeconds 12
```

O modo real chama explicitamente o `codex.cmd` do NVM em `v26.13.1`, construído a partir de `LOCALAPPDATA`. O `codex` encontrado no PATH é registrado apenas como categoria normalizada para mostrar diferenças entre terminais; ele não substitui o wrapper fixado. Se o wrapper fixado não existir, o script retorna `pinned_wrapper_missing` **antes** de executar Codex. O marcador exclusivo `tmp/codex-context-probe.real.once` é criado antes da única chamada e permanece mesmo após falha; executar o comando novamente retorna `duplicate_blocked`. Preserve o marcador e peça revisão antes de qualquer novo experimento.

Para testar o script sem executar Codex:

```powershell
pwsh -NoProfile -File scripts/windows/probe-codex-context.ps1 -Mode Fake -FakeOutcome Success
pwsh -NoProfile -File scripts/windows/probe-codex-context.ps1 -Mode Fake -FakeOutcome Permission
```

O JSON contém somente `status`, categoria fixa, exit code, contagem de bytes, SHA-256 dos dois fluxos, contagem de tipos de evento conhecidos, timestamps e metadados normalizados: forma das flags, tipo de executável resolvido, diretório de trabalho classificado, nomes de variáveis presentes, versão principal do PowerShell e indicadores de identidade. O caminho do sandbox, o texto da tarefa, stdout, stderr, valores de ambiente e credenciais não são impressos nem gravados. Os sandboxes fake permanecem vazios e separados sob `tmp`.

`status=passed` e exit code 0 exigem exit 0 da CLI, `thread.started`, `turn.completed` e a resposta sintética esperada. `failed`, `invocation_inconclusive` ou `preflight_failed` retornam exit code 1. A categoria `permission` indica apenas que um padrão fixo apareceu na saída; não identifica o recurso negado. Compare o exit, bytes, hashes e eventos com o diagnóstico anterior: mesma categoria e tamanho com hash diferente não provam a mesma causa. O contexto de PowerShell comum ainda pode diferir em outras variáveis do probe anterior, que não foi totalmente registrado.
