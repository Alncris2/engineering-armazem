# Orchestrator

`workflow.py` executa um grafo LangGraph de suporte com `PostgresSaver`. O `thread_id` é o UUID da run no Core. O fluxo usa preflight de leitura, dois checkpoints supervisionados e validação de um estado OpenSquad arquivado; não inicia nem retoma a pipeline OpenSquad. `workflow_leases` impede duas runs simultâneas sobre o `state.json` compartilhado.

As dependências fixadas em `uv.lock` foram instaladas na venv local `.venv-workspace`. `oracledb` é extra opcional para o adaptador Oracle; nenhum agente LangChain foi implementado. Consulte [architecture-v2.md](../../docs/architecture-v2.md) para comandos e limites.
