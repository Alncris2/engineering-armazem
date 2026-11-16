# Matriz de integração e evidência

Legenda: confirmado = arquivo ou comando observado; parcial = documentação local sem teste; proposta = contrato a implementar.

| Integração/capacidade | Estado | Evidência e limite |
|---|---|---|
| Maestri lança Claude Code/Codex | Parcial | `maestri-manager/SKILL.md` documenta `recruit --preset "Claude Code"` e `--preset "Codex"`; presets da instalação não foram listados. |
| Comando personalizado | Parcial | Mesma skill documenta `recruit --command`; não houve execução. |
| Supervisão e múltiplas execuções | Parcial | `maestri list`, `ask`, `check`, `dismiss`, canvas/bands/floors documentados nas skills locais; limites, persistência e telemetria não testados. |
| API, hooks, plugins, MCP do Maestri | Não confirmado | Nenhuma especificação de API/hooks/plugins/MCP identificada na documentação inspecionada. Não basear MVP nessas interfaces. |
| Serviço local no Maestri | Proposta | Terminal com comando local ou portal para URL loopback é candidato; validar no Maestri real, inclusive origem/CORS/autenticação. |
| OpenSquad inicialização externa | Parcial | `README.md` documenta `/opensquad run`; `tools/opensquad/hivemind.ps1` contém wrapper Hivemind `doctor/support`, preflight e spawn. Wrapper é específico do Hivemind; não é API Maestri. |
| Estado/artefatos OpenSquad | Confirmado em código | `runner.pipeline.md`: estado em `state.json`, artefatos em `output/{run_id}`, versionamento por `artifact.mjs`. Sem run de teste nesta etapa. |
| Gates | Confirmado em código | `route.mjs`, `support-gate.mjs`; suporte só entrega a João após relatório concluído e handoff aprovado. Preservar escolha humana. |
| Ticket Jira | Parcial | Support pipeline recebe código do card no checkpoint; vínculo estruturado run-ticket ainda não existe. |
| Sessão Claude/Codex | Proposta | Capturar identificador emitido pela CLI/host, quando documentado e testado; usar ID interno mesmo se externo indisponível. |
| Concorrência | Bloqueada no diretório atual | `state.json` único por squad; `hivemind.ps1` recusa outra run running/waiting. Exige instâncias isoladas. |
| Retomada | Parcial | Runner instrui retomar mesmo `runId` após decisão; testar falha de processo e reconciliação antes de automatizar. |
| Eventos estruturados | Proposta | `state.json` é snapshot, sem stream durável de eventos identificado. Adaptador emitirá eventos a partir de transições observadas, com sequência e idempotência. |
| MCP Oracle/Grafana/Jira | Parcial | Pipeline de suporte referencia Oracle SELECT e Grafana; disponibilidade, permissões e schemas MCP desta sessão não foram testados. Jira é rascunho, não publicação. |

Experiência Maestri sugerida: terminal ou preset executa cliente do controle local com `run_id`; canvas mostra agente e logs; link do dashboard local abre progresso e approvals. Primeiro protótipo deve demonstrar comando local e portal sem pressupor API ou plugin Maestri.
