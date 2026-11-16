# Arquitetura proposta — fase 1 (histórico)

Este desenho registra as hipóteses iniciais. A arquitetura atual, sem MCP e com CLI compartilhada por interfaces, está em [architecture-v2.md](architecture-v2.md).

Estado: desenho, sem serviços instalados ou pipelines executadas. O repositório Git local foi inicializado em 2026-11-13 para a Etapa 01; os projetos corporativos permaneceram intocados. Inventário e limites atuais: `etapa-01-validation.md`.

```text
Maestri (canvas, terminais Claude/Codex)
  -> interface de lançamento a validar -> API Laravel (controle, RBAC, auditoria)
  -> LangGraph (máquina de estados, checkpoints duráveis)
       -> adaptador OpenSquad (runner existente em instância isolada)
       -> executores Claude/Codex (sessões externas)
       -> conectores MCP Oracle/Grafana/Jira (leitura por padrão)
  -> PostgreSQL (transações, eventos, artefatos metadados) + pgvector (RAG)
```

Laravel é o plano de controle; LangGraph é o dono da progressão da run. Persistir comandos em fila transacional com chave idempotente, processar por worker Python e devolver eventos ao banco. Um único componente decide a próxima etapa. OpenSquad continua autoridade dos seus gates; LangGraph não salta checkpoints. Arquivos de artefato ficam em diretório por run, fora do banco; guardar hash, tamanho, tipo, caminho relativo e controle de acesso no PostgreSQL. Não copiar automaticamente logs, prompts ou dados Oracle para RAG.

Para cada execução, preparar uma cópia ou worktree **do workspace OpenSquad** com `state.json` exclusivo. O `output/{run_id}` já separa artefatos, mas não resolve a colisão do estado ativo. Manter lock de instância e vínculo `run_id -> caminho de instância`; jamais usar duas runs no mesmo `squads/webagil-dev/state.json`. Para desenvolvimento de código, criar worktree próprio do repositório alvo, registrar branch, HEAD e base; não trazer QAS/qualid para branch da demanda. O adaptador deve primeiro ser testado em cópia descartável, com gates reais e sem alterar o runner original.

Fluxo: criar run -> validar projeto/ticket/ambiente -> reservar instância -> preflight -> iniciar executor -> registrar step/eventos -> aguardar aprovação humana quando aplicável -> validar artefatos e gate -> avançar -> arquivar estado -> concluir. Ao reiniciar, conciliar banco, processo e `state.json`; estado incerto vai a `needs_reconciliation`, nunca reinicia step com efeito externo automaticamente.

Segurança: serviços escutam em loopback, autenticação entre API e worker, permissões por projeto e ambiente, segredos no Windows Credential Manager/secret store aprovado, sem valores em logs. MCP Oracle somente SELECT na fase inicial; Grafana leitura; Jira leitura e rascunho local. Ações de escrita futuras exigem permissão específica e aprovação rastreável.

Hospedagem Windows proposta: PostgreSQL como Windows Service; API Laravel atrás de IIS/FastCGI ou Apache já homologado (escolher após inventário), com worker de filas em serviço separado; worker LangGraph em venv Python e adaptador Node/OpenSquad como processos filhos supervisionados por serviço Windows aprovado (por exemplo, WinSW, sujeito a instalação autorizada). Não usar `artisan serve` como serviço persistente. Configurar início automático, restart com limite, health checks, Event Log e arquivos de log com rotação por serviço. Na queda, reconciliar PID, heartbeat, checkpoint e hash de artefatos antes de retomar. Instâncias e worktrees sob raiz própria com ACL por conta de serviço; nunca compartilhar diretório de estado entre runs. MCPs podem ser processos locais por sessão ou serviços loopback, conforme transporte efetivamente suportado por cada conector; mapear antes de escolher.

## Evidência e limites

- `C:\htdocs\squad-ia\README.md`: comando `/opensquad run webagil-dev support`, saída por run, checkpoints.
- `C:\htdocs\squad-ia\_opensquad\core\runner.pipeline.md`: `state.json` obrigatório, preflight, validações e retomada manual.
- `C:\htdocs\squad-ia\tools\opensquad\route.mjs` e `support-gate.mjs`: roteamento e gate em CLI Node.
- Maestri: documentação local em `C:\Users\alan.cristian\.agents\skills\maestri-manager\SKILL.md` e `maestri-workspace\SKILL.md`; CLI instalado em `AppData\Local\Programs\Maestri\resources\cli\maestri.exe`, mas comandos operacionais exigem `MAESTRI_PIPE` de um terminal Maestri. Integração exata continua hipótese.
