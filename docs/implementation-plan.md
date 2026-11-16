# Plano de implementação ordenado

Cada tarefa abaixo gera mudança apenas neste novo workspace até aprovação de integração com sistemas existentes.

1. **Resolver ambiente base.** Dependências: nenhuma. Confirmar Maestri executável/presets e escolher Python, PostgreSQL/pgvector e gerenciador de serviço Windows com versões compatíveis. Aceite: comandos/versionamento e matriz de compatibilidade registrados; instalação autorizada separadamente.
2. **Provar Maestri local.** Depende 1. Em ambiente de teste, validar preset Claude/Codex, `--command`, múltiplos terminais e abertura do dashboard loopback. Aceite: transcrições sem segredo e limites documentados; não exigir API não demonstrada.
3. **Criar banco e migrações do controle.** Depende 1. Implementar oito entidades, FK, uniques, transições e outbox de eventos. Aceite: migração reversível e testes de unicidade/idempotência.
4. **API Laravel de controle.** Depende 3. Endpoints versionados de projetos, tickets, runs, eventos, artefatos e approvals; RBAC. Aceite: contrato OpenAPI, teste de acesso negado e chave idempotente.
5. **Worker LangGraph mínimo.** Depende 3. Checkpointer PostgreSQL, fila/outbox, reconciliação e health. Aceite: retomada após kill em step simulado sem duplicação.
6. **Adaptador OpenSquad isolado.** Depende 2, 4, 5. Criar instância por run, executar preflight e CLI/gates originais sem editar OpenSquad corporativo. Aceite: duas runs simultâneas em instâncias distintas, estados/artefatos independentes, gate de suporte preservado.
7. **Executores Claude/Codex.** Depende 2, 6. Capturar sessão, PID, saída redigida e correlação. Aceite: retomada ou sinalização `needs_reconciliation` após queda; nenhuma sessão órfã silenciosa.
8. **MCPs leitura e vínculo Jira.** Depende 4, 5. Mapear capacidades reais e políticas por ambiente. Aceite: fluxo de suporte lê ticket/log/SELECT com auditoria, sem operações de escrita; indisponibilidade gera erro tipado.
9. **RAG controlado.** Depende 3, 8. Política de fontes, permissão e atualização; ingestão aprovada em pgvector. Aceite: avaliação com citações e teste de isolamento entre projetos; nenhuma cópia de dados sensíveis sem política.
10. **Operação Windows.** Depende 4-9. Instalação de serviços, logs rotativos, recovery, backup/restore e atualização. Aceite: reboot, queda de worker, restauração e rotação de credenciais ensaiados.

Gate de saída da fase 1: esclarecer bloqueios em `risks.md`; não iniciar instalação ou mudanças corporativas a partir deste documento.
