# Arquitetura local — LangGraph + CLI

```text
PowerShell comum / Maestri / Orca (quando disponível)
                    │
            workspace.ps1 → workspace.py
                    ├─ API Laravel em loopback: projetos, tickets, runs, sessões, memória
                    ├─ Jira REST GET: metadados do card, credencial local existente
                    ├─ Git CLI / Oracle SELECT / Loki GET: adaptadores de leitura
                    ├─ Importador OpenSquad: snapshots arquivados, somente leitura
                    └─ LangGraph: workflow de suporte e grafo de desenvolvimento
                           └─ PostgreSQL: checkpoints, runs, eventos e lease por squad
```

O terminal ou interface não possui a lógica de negócio. Maestri e Orca chamam os mesmos comandos, que usam a API local e o processo Python. Não há frontend próprio. O serviço Python usa `StateGraph` e `PostgresSaver` diretamente. `langchain-core` é dependência transitiva do pacote LangGraph; nenhum agente LangChain foi implementado.

O workflow de suporte está em `services/orchestrator/workflow.py`. Ele identifica o ticket, recupera a contagem de runs anteriores, executa o preflight somente de leitura do OpenSquad, aguarda investigação supervisionada, exige uma decisão humana e verifica o `state.json` arquivado antes de persistir. Ele **não inicia nem retoma** uma pipeline OpenSquad: o wrapper comprovado em `C:\htdocs\squad-ia\tools\opensquad\hivemind.ps1` depende de Hivemind e usa um `state.json` global. O lease `workflow_leases` impede duas runs de suporte simultâneas nesse recurso. Uma run interrompida retoma pelo mesmo `thread_id`/UUID no PostgreSQL. O estado `waiting_approval` não é aprovado automaticamente.

O Core mantém o OpenSquad como autoridade sobre seus próprios gates. A validação atual confere o estado arquivado `completed`, a etapa final, o horário de conclusão e a presença de arquivos. Ela não substitui revisão funcional nem comprova cada decisão humana histórica. O RAG semântico com pgvector permanece opcional; a busca inicial usa texto em tickets e evidências.

Jira usa GET da API oficial, sem MCP. Oracle e Grafana/Loki têm adaptadores de leitura preparados; testes remotos dependem de configuração específica. Git CLI foi validado em repositório local. Claude e Orca não estavam no PATH da sessão; Codex CLI foi detectado. Nenhuma credencial é copiada para este monorepositório.

## Comandos

`pwsh -File scripts/windows/workspace.ps1 --json projects list`

`pwsh -File scripts/windows/workspace.ps1 --json tickets history EVOLOG-31599`

`pwsh -File scripts/windows/workspace.ps1 --json tickets sync webagil EVOLOG-31599`

`pwsh -File scripts/windows/workspace.ps1 --json memory search EVOLOG-31599`

`pwsh -File scripts/windows/workspace.ps1 --json pipelines start --project webagil --ticket EVOLOG-31599 --key CHAVE-ESTAVEL`

`pwsh -File scripts/windows/workspace.ps1 --json pipelines status --run UUID`

`pwsh -File scripts/windows/workspace.ps1 --json pipelines resume --run UUID --decision investigated --source-run RUN_ID`

`pwsh -File scripts/windows/workspace.ps1 --json pipelines resume --run UUID --decision approve`

`pwsh -File scripts/windows/workspace.ps1 --json development start --thread dev-demo --issue EVOLOG-31599 --scenario config/development/simulation-example.json`

`pwsh -File scripts/windows/workspace.ps1 --json development status --thread dev-demo --scenario config/development/simulation-example.json`

`pwsh -File scripts/windows/workspace.ps1 --json development resume --thread dev-demo --scenario config/development/simulation-example.json --decision resume`

O grafo de desenvolvimento está descrito em [development-graph.md](development-graph.md). Os cenários atuais simulam executor e aprovações para validar transições, checkpoints e recuperação; `done` nesse modo não comprova implementação, revisão ou publicação real.

Há também um adaptador experimental Codex CLI restrito ao planejamento read-only em sandbox local. Use `development start --executor codex --task-file CAMINHO` e `development status --thread ID`; detalhes e limites em [development-graph.md](development-graph.md). Nenhuma etapa de escrita do grafo foi conectada ao Codex.

Os comandos `pipelines` exigem a venv em `services/orchestrator/.venv-workspace`; os comandos da API exigem o Laravel em `127.0.0.1:8088`. `--timeout` limita chamadas externas. Saída é um envelope JSON; diagnósticos estruturados vão para stderr. Não passe credenciais na linha de comando.

## Limites operacionais

- A run real de validação de suporte permanece em `waiting_approval`, aguardando decisão humana. O lease permanece ativo para proteger o estado compartilhado.
- O launcher do OpenSquad é ligado ao Hivemind; ainda não há adaptador independente de execução ou cópia isolada comprovada.
- Oracle, Grafana e Orca não tiveram teste remoto funcional nesta etapa. Claude Code não estava acessível pelo PATH.
- A API Laravel não tem autenticação multiusuário e deve ficar em loopback. `artisan serve` é apenas para teste interativo local.
- Os arquivos do repositório estão não rastreados no Git local e `.git` não está gravável neste perfil; não há commit.
