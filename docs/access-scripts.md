# Acessos locais e pastas de demanda

Execute em PowerShell 7 a partir da raiz do AI Engineering Workspace. Os scripts leem as configurações existentes no momento da execução. Nenhuma credencial, chave SSH ou cópia de `.env` é guardada neste repositório.

## Conferir fontes

```powershell
.\scripts\windows\access-doctor.ps1
```

O comando verifica arquivos, credencial Jira e os seis destinos Oracle sem abrir conexões. O mapeamento Oracle vem de `C:\htdocs\squad-ia\.mcp.json`; o Grafana usa `C:\htdocs\squad-ia\.env`; os perfis SSH vêm do `settings.json` do Windows Terminal.

## Jira e pasta da demanda

```powershell
.\adapters\jira\get-issue.ps1 -Key EVOLOG-33092
.\scripts\windows\demand.ps1 -Key EVOLOG-33092 -Repository C:\htdocs\webagil_2.0 -BaseBranch dev -WorktreeName webagil-back -Plan
.\scripts\windows\demand.ps1 -Key EVOLOG-33092 -Repository C:\htdocs\webagil_2.0 -BaseBranch dev -WorktreeName webagil-back
```

`get-issue.ps1` usa a credencial já salva por `baixar-jira` e faz GET direto ao Jira. `demand.ps1` cria `C:\htdocs\Demandas\<JIRA>`, chama a função `baixar-jira` do perfil para XML, anexos e referências, cria o worktree dentro da pasta e publica a branch com `git push -u origin`. A branch nasce em `origin/<BaseBranch>`, mas o upstream final deve ser `origin/<JIRA>`. Se o download, o push ou a conferência de upstream falhar, o comando termina com erro; examine a pasta e o Git antes de repetir. A função `baixar-jira` pode baixar cards referenciados recursivamente e atualizar arquivos existentes.

Para outra base ou repositório, informe os parâmetros explicitamente. O script não altera o checkout principal nem aceita uma branch local já existente, para evitar associar um worktree à branch errada.

## Oracle somente leitura

```powershell
.\scripts\windows\oracle-read.ps1 -Connection oracle-webagil-prd -Probe -MaxRows 1
.\scripts\windows\oracle-read.ps1 -Connection oracle-webagil-prd -SqlFile .\consulta.sql -ParamsFile .\params.json -MaxRows 20
```

O SQL deve estar em arquivo, ser uma única consulta `SELECT` ou `WITH` e usar binds (`:nrAtendi`, por exemplo). O JSON de parâmetros é um objeto como `{"nrAtendi":2077039}`. O cliente configura transação `READ ONLY`, tempo limite de 30 segundos e no máximo 200 linhas. Evite salvar valores sensíveis em arquivos versionados. `-Probe` consulta apenas nome do banco e schema atual. Ambientes válidos: `oracle-webagil-dev`, `oracle-webagil-qas`, `oracle-webagil-prd`, `oracle-warehouse-dev`, `oracle-warehouse-qas`, `oracle-warehouse-prd`.

## SSH e Grafana

```powershell
.\scripts\windows\ssh-profile.ps1 -Action list
.\scripts\windows\ssh-profile.ps1 -Action open -Server prd-back-novo
.\scripts\windows\grafana-read.ps1 -Query '{app="webagil"}' -Start 0 -End 1
```

`ssh-profile.ps1` abre o perfil existente do Windows Terminal, sem copiar o comando SSH ou sua chave. Os aliases são `qas-back`, `prd-back-novo` e `prd-back-antigo`. `grafana-read.ps1` usa token, se configurado, ou usuário/senha já existentes no `.env`, e restaura as variáveis de processo ao terminar. Informe horários Unix em nanossegundos para uma consulta Loki real; o exemplo ilustra somente a forma do comando.

## Verificação feita em 2026-11-15

O GET de EVOLOG-33092 retornou HTTP 200 e ID Jira 113480. O preflight Oracle WebÁgil PRD retornou DB `ORCL` e schema `ROOT`. A pasta `C:\htdocs\Demandas\EVOLOG-33092` recebeu o XML e um anexo via `baixar-jira`. O worktree `webagil-back` foi criado a partir de `origin/dev`, HEAD `c1860a0abb4a724f6882c43886e009e93bd225c0`, branch `EVOLOG-33092`, upstream `origin/EVOLOG-33092`.
