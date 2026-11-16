# Etapa 01 — validação da fundação Windows

Data: 2026-11-13. Escopo: consultas locais somente leitura, criação de arquivos neste workspace e `git init` local. Não houve instalação, conexão corporativa, execução de pipeline, nem alteração de runtime global.

Atualização posterior em 2026-11-13: o usuário instalou Python 3.13.7 no pyenv-win e informou que está instalando PostgreSQL. Foi executado `pyenv local 3.13.7` somente neste workspace. `pyenv version` e `python --version` confirmaram 3.13.7; a seleção global permanece em 2.7.18. O arquivo `.python-version` registra a seleção local. `C:\Program Files\PostgreSQL\18\bin\psql.exe` já existe, mas nenhum serviço PostgreSQL apareceu na consulta; instalação e pgvector ainda não foram validados.

O teste de `python -m venv services/orchestrator/.venv` criou o interpretador, mas falhou em `ensurepip` por `PermissionError` no diretório temporário, inclusive ao usar `tmp/` dentro deste workspace. Assim, `.venv` está incompleto e sem pip; permanece ignorado pelo Git e não deve ser usado para instalar dependências. A tentativa de remover recursivamente apenas esse venv e `tmp/` foi rejeitada pela política automática de aprovação desta sessão. A limpeza fica pendente em um PowerShell com permissão adequada.

Validação posterior do PostgreSQL: `pg_config --version` e `psql --version` retornaram 18.7 e o serviço `postgresql-x64-18` está ativo. Os arquivos `vector.dll` e `vector.control` não existem. Visual Studio 2019 Build Tools com C++ está presente; `git ls-remote` para o repositório oficial do pgvector falhou no proxy `127.0.0.1:9`. O procedimento pendente está em [pgvector-windows.md](pgvector-windows.md). Não houve instalação da extensão nem conexão ao banco.

Após a instalação pelo usuário, nova verificação confirmou `lib\vector.dll`, `share\extension\vector.control` e `share\extension\vector--0.8.7.sql`; o control declara versão padrão 0.8.7. O serviço PostgreSQL 18.7 está ativo. `psql -X -w -U postgres -d postgres` não conectou (`fe_sendauth: no password supplied`), então habilitação em um banco e consulta a `pg_extension` seguem pendentes. A descrição anterior registra o estado antes da instalação.

## Controle de versão

`git init` criou `.git` local na branch `main`; `git rev-parse --show-toplevel` retornou este workspace e `git remote -v` não mostrou remotos. Os arquivos do projeto estão presentes e aparecem como não rastreados. A tentativa de `git add` retornou `fatal: Unable to create .../.git/index.lock: Permission denied`: o perfil desta sessão permite leitura de `.git`, mas bloqueia escrita no índice. Por isso **não há commit inicial** e o critério de arquivos efetivamente versionados permanece pendente. Não foi feito push. `git diff --check` não encontrou erro, mas não verifica arquivos ainda não rastreados.

`git check-ignore -v` confirmou regras para `.env`, `.env.local`, `vendor/`, `.venv/`, `node_modules/`, `output/` e `state.json`. As oito pastas de componentes contêm `.gitkeep` e poderão ser rastreadas quando a escrita em `.git` estiver disponível.

## Maestri

| Verificação | Resultado e evidência |
|---|---|
| Instalação e versão | `C:\Users\alan.cristian\AppData\Local\Programs\Maestri\Maestri.exe`, atalho no menu Iniciar; metadados `ProductVersion=0.30.8.0`, `FileVersion=0.30.8`. CLI em `resources\cli\maestri.exe`; `--version` retornou `79a7791b` (hash abreviado de build). `resources\build-info.json` registra build 129. |
| Acesso ao CLI | `Get-Command maestri` e `where.exe maestri` não encontraram comando no PATH. `MAESTRI_CLI` e `MAESTRI_PIPE` não estão definidos nesta sessão. CLI por caminho absoluto existe. |
| Comandos | `--help`, `preset list`, `list`, `workspace list` e `floor list` por caminho absoluto retornaram `only available inside Maestri terminals (MAESTRI_PIPE not set)` e exit code 1. Portanto, lista efetiva de comandos e estados não pôde ser lida fora de um terminal Maestri. |
| Presets Claude/Codex | A skill local `maestri-manager/SKILL.md` documenta `maestri preset list` e `recruit --preset "Claude Code"/"Codex"`. Os presets configurados nesta instalação não foram listados. |
| Comando personalizado e diretório | A mesma skill documenta `recruit --command` e `--dir`; execução real não testada. |
| Terminal do workspace e múltiplos agentes | `maestri-workspace/SKILL.md` documenta workspace/floors; `maestri-manager/SKILL.md` documenta `recruit`, `list`, conexões e múltiplos terminais. Abertura e concorrência reais não testadas nesta sessão. |
| Ferramentas externas | Skills locais mencionam portal, notas e agentes. Nenhuma API, hook, MCP ou plugin programático do Maestri foi verificado. A integração proposta permanece terminal/comando local, sujeita a prova dentro do Maestri. |

Próxima prova isolada: entrar num terminal do próprio Maestri para executar `maestri --help`, `maestri preset list`, `maestri list` e um comando local inofensivo em terminal associado a este workspace. Abrir mais de um agente só numa etapa autorizada para o teste, sem envolver o OpenSquad original.

## Inventário Windows

Consultas: `Get-Command`, comandos de versão, `pyenv versions`, `nvs ls`, `nvm list`, `php -m`, `php --ini`, busca de serviços PostgreSQL e diretórios de instalação. Ausência no PATH ou nos locais pesquisados não prova ausência total de instalação.

| Dependência | Evidência observada | Estado para este projeto |
|---|---|---|
| Windows / PowerShell | NT `10.0.26200.0`; `pwsh` `7.6.6` | Disponível, sessão nativa Windows. |
| Git | `2.55.0.windows.5`, `C:\Program Files\Git\cmd\git.exe` | Disponível. |
| PHP / Composer | PHP CLI `8.5.12` ZTS; Composer `2.10.3` | Base compatível em versão com Laravel 13; instalar o framework e testar a aplicação depois. Composer emitiu aviso do Xdebug. |
| Extensões PHP | `php -m`: extensões básicas Laravel presentes; `oci8`, `PDO_OCI`, `pdo_mysql` presentes; `pdo_pgsql` e `pgsql` ausentes | Driver PostgreSQL para a API está ausente no PHP ativo. Não mudar este PHP global. |
| Node / npm | Node `25.2.1`, npm `11.8.0` | Disponível; versão ativa não valida compatibilidade com OpenSquad ou projetos corporativos. |
| Gerenciadores Node | NVS `1.7.1`, com Node `25.2.1`, `14.21.3`, `10.18.0`; nvm `1.2.2`, sem instalações reconhecidas; fnm ausente do PATH | Fixar Node por processo do adapter, sem trocar a versão global. |
| Python / pyenv-win | Python global `2.7.18`; versões `3.8.10` e `3.13.7` instaladas; `pyenv local 3.13.7` neste workspace, confirmado por `python --version` | Base Python compatível em versão com LangGraph; dependências e execução do worker ainda não testadas. |
| PostgreSQL / pgvector | PostgreSQL 18.7 confirmado por `psql` e `pg_config` por caminho absoluto; serviço `postgresql-x64-18` ativo; arquivos pgvector 0.8.7 presentes | Instalação dos arquivos confirmada; habilitação da extensão por banco ainda não verificada. |
| Claude Code | `claude --version`: `2.1.310` | CLI disponível; autenticação e execução não testadas. |
| Codex | `codex --version`: `0.167.2` | CLI disponível; aviso de permissão em diretório temporário, sem falha do comando de versão. |
| Maestri | App `0.30.8`, CLI por caminho absoluto, hash `79a7791b` | Instalado, mas comandos operacionais indisponíveis fora do terminal Maestri. |

## Matriz de compatibilidade

| Componente pretendido | Requisito/fonte | Resultado local | Decisão desta etapa |
|---|---|---|---|
| Laravel 13 | [Requisitos oficiais: PHP >=8.3 e extensões](https://laravel.com/framework/docs/deployment); [notas de release: PHP 8.3–8.5](https://laravel.com/framework/docs/13.x/releases) | PHP 8.5.12 e extensões básicas presentes; `pdo_pgsql` ausente | PHP serve como base de linguagem; provisionar driver PostgreSQL isoladamente antes da API. Nenhum projeto Laravel criado. |
| LangGraph Python | [Projeto oficial: Python >=3.10](https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/pyproject.toml) | Python 3.13.7 selecionado localmente | Requisito de versão atendido; venv ainda incompleto por falha de permissão no `ensurepip`. |
| PostgreSQL + pgvector | [pgvector: instruções de build Windows e versão vinculada ao PostgreSQL](https://github.com/pgvector/pgvector/blob/master/README.md) | PostgreSQL 18.7 e serviço ativos; arquivos pgvector 0.8.7 presentes | Validar `pg_available_extensions` e `pg_extension` no banco escolhido com acesso autorizado. |
| Adapter Node/OpenSquad | Documentos `architecture.md` e `integration-matrix.md`; runner corporativo não executado | Node 25 ativo, 14 também no NVS | Compatibilidade do adapter ainda não demonstrada; usar seleção por processo e cópia isolada em teste posterior. |
| Maestri | Skills locais e CLI instalado | CLI exige `MAESTRI_PIPE` | Validar presets e execução dentro do app antes de desenhar contrato de lançamento. |

## Bloqueios objetivos

1. pgvector instalado em arquivos, mas não validado por SQL; `pdo_pgsql` ausente no PHP ativo.
2. Sessão atual não é terminal Maestri; presets, comando personalizado e concorrência não tiveram teste funcional.
3. Compatibilidade do Node do futuro adapter com uma cópia isolada do OpenSquad não foi testada.
4. Escrita em `.git` bloqueada pelo perfil da sessão; `git add` e commit inicial pendentes, apesar de `git init` concluído.
5. O venv de teste não tem pip após falha de `ensurepip`; limpeza recursiva rejeitada pela política automática desta sessão.

Próxima tarefa recomendada: **validar o pgvector por SQL no banco escolhido** com acesso local autorizado. Em seguida, limpar o venv incompleto, corrigir o acesso ao diretório temporário e recriar o venv do orquestrador com Python 3.13.7. A prova do Maestri dentro do próprio app também segue pendente.
