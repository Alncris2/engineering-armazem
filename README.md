# AI Engineering Workspace

Monorepositório Windows nativo para persistir projetos, chamados Jira, runs e histórico de investigações. Maestri e terminais PowerShell usam a mesma CLI; Orca poderá usar os mesmos comandos quando estiver instalado. A API Laravel serve apenas em loopback. Não há frontend próprio.

| Caminho | Responsabilidade |
|---|---|
| `apps/control-api` | API Laravel 13, migrations, importador e testes |
| `adapters/opensquad` | Contrato de importação somente de leitura |
| `services/orchestrator` | Workflows LangGraph de suporte e desenvolvimento, com checkpoints PostgreSQL |
| `services/knowledge` | Contrato de recuperação futura |
| `config/projects` | Catálogo e templates futuros |
| `scripts/windows` | Instalação, inicialização e cliente de histórico |
| `docs/core-v1.md` | Instalação, endpoints e limites operacionais |

Comece em [docs/architecture-v2.md](docs/architecture-v2.md). Configurações locais ficam em `apps/control-api/.env`, que é ignorado pelo Git. O OpenSquad original é lido, nunca escrito. O importador exige o `state.json` arquivado em `output/{run_id}`.

A arquitetura atual de CLI e LangGraph está em [docs/architecture-v2.md](docs/architecture-v2.md).

O catálogo de repositórios e tecnologias está em [docs/project-catalog.md](docs/project-catalog.md).

A captura de sessões Codex e Claude Code está documentada em [docs/session-capture.md](docs/session-capture.md).

A documentação do Core v1 está em [docs/core-v1.md](docs/core-v1.md). A antiga ponte Jira MCP está registrada em [docs/jira-mcp.md](docs/jira-mcp.md) apenas como histórico; a integração ativa usa Jira REST GET.

Os comandos para Jira, pasta da demanda, worktree com upstream, Oracle, SSH e Grafana estão em [docs/access-scripts.md](docs/access-scripts.md).
