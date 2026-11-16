# Riscos e bloqueios antes da implementação

| Prioridade | Risco/bloqueio | Evidência atual | Resolução necessária |
|---|---|---|---|
| Alto | Maestri só executável dentro do próprio terminal | App 0.30.8 e CLI localizados; comandos operacionais retornam `MAESTRI_PIPE not set` nesta sessão | Validar presets, comando customizado e terminal do workspace em sessão Maestri real. |
| Crítico | Concorrência OpenSquad | `state.json` único e `hivemind.ps1` bloqueia segunda run | Provar isolamento por instância e locks em cópia, preservar gates. |
| Médio | Venv Python ainda incompleto | Python 3.13.7 instalado pelo usuário e selecionado neste workspace via `.python-version`; `ensurepip` falhou com `PermissionError` no diretório temporário | Limpar o venv de teste, corrigir permissão temporária e recriar venv exclusivo antes de instalar LangGraph. |
| Médio | pgvector ainda não validado por SQL | PostgreSQL 18.7 e serviço `postgresql-x64-18` ativos; arquivos pgvector 0.8.7 presentes; `psql -w` retornou `no password supplied` | Com acesso local autorizado, consultar `pg_available_extensions` e `pg_extension` no banco escolhido; `pdo_pgsql` também segue ausente no PHP ativo. |
| Alto | Compatibilidade por projeto | Node ativo 25, Server declarado Node 14; Angular 10; PHP ativo 8.5 | Fixar versões por processo/worktree; validar Laravel 13 e extensões. |
| Alto | Retomada após queda não testada | Runner instrui retomada do mesmo `runId`; não há stream durável | Testar reconciliação e checkpoint sem repetição de ações externas. |
| Médio | Integração Maestri via API/MCP desconhecida | Nenhuma especificação encontrada nas skills inspecionadas | Prototipar terminal + dashboard; investigar API oficial/local apenas se necessária. |
| Médio | MCPs não inventariados na sessão | Referências no pipeline, sem teste dos conectores | Verificar ferramentas, escopos, permissões e mascaramento antes de uso. |
| Médio | Permissões locais | Avisos Composer temp, Codex temp, profile/starship | Corrigir diretórios/permissões após avaliar impacto; não usar avisos como prova de falha funcional. |
| Médio | Conteúdo sensível em RAG/eventos | Evidências podem incluir dados Oracle/Jira/logs | Política de classificação, retenção, redaction e ACL antes de ingestão. |

Limite de evidência: nenhuma pipeline, banco, MCP ou instalação foi executada/testada funcionalmente nesta fase. Os contratos e arquitetura são propostas; a documentação local do Maestri mostra capacidades previstas, não comprova disponibilidade nesta sessão.
