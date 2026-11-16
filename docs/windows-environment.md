# Inventário Windows — 2026-11-12 (histórico)

Este inventário é a fotografia anterior à Etapa 01. O inventário atualizado de 2026-11-13 e a matriz de compatibilidade estão em [etapa-01-validation.md](etapa-01-validation.md).

Consultas somente leitura na sessão PowerShell atual. `Get-Command`, `--version`, inspeção de diretórios. Ausente no PATH não prova ausência de instalação.

| Item | Resultado observado | Implicação |
|---|---|---|
| Windows | NT 10.0.26200.0 | Confirmar edição/build com `winver` fora do sandbox antes de suporte operacional. |
| PowerShell | 7.6.6 | Disponível. Profile gerou aviso de permissão/modo de linguagem. |
| Git | 2.55.0.windows.5, `C:\Program Files\Git\cmd\git.exe` | Disponível; pasta deste projeto não tem `.git`. |
| Node/npm | 25.2.1 / 11.8.0, NVS em `%LOCALAPPDATA%\nvs\node\25.2.1\x64` | Não serve de validação para Server Node 14 ou Angular 10; fixar versões por projeto. |
| Gerenciadores Node | nvm 1.2.2; NVS inferido do caminho ativo; fnm não encontrado | Verificar inventário NVS/nvm e evitar mistura de PATH. |
| Python | `python` 2.7.18 via pyenv-win shim; versões 2.7.18 e 3.8.10 em pyenv | Falta Python moderno verificado para LangGraph; fastapi 3.7.4 também não está instalado no pyenv inspecionado. Isolar venv por serviço. |
| PHP/Composer | PHP 8.5.12 `C:\php8512\php.exe`; Composer 2.10.3 | Confirmar matriz Laravel 13 e extensões Oracle/pgsql em ambiente específico. Composer avisou `sys_temp_dir` inacessível e Xdebug ativo. |
| PostgreSQL/pgvector | `psql` e `pg_config` não encontrados; nenhum diretório PostgreSQL encontrado em Program Files | Instalação e extensão não confirmadas. Não foi feita conexão nem consulta SQL. |
| Claude Code | 2.1.310 via NVS `claude.ps1` | CLI presente; autenticação/sessão não testadas. |
| Codex | 0.167.2 via NVS `codex.ps1` | CLI presente; avisos de permissão em pasta temporária Codex. |
| Maestri | `maestri` não encontrado; `MAESTRI_CLI` vazio | Documentação local existe; instalação/binário e API não confirmados nesta sessão. |
| OpenSquad | `C:\htdocs\squad-ia`, arquivos de runner, squad, gates e dashboard presentes | Estrutura inspecionada; pipeline não iniciada. |
| Ambientes virtuais | `VIRTUAL_ENV` não ativo; `VIRTUAL_ENV_DISABLE_PROMPT=1` | Criar venv dedicado após aprovação de dependências. |

Dependências de implementação ainda a validar/instalar com autorização: Python suportado por versão escolhida do LangGraph, PostgreSQL Windows e pgvector compatível, drivers PHP `pdo_pgsql`/Oracle conforme necessidade, serviço de processo aprovado, credenciais de serviço e localização executável Maestri. Não instalar nesta fase.
