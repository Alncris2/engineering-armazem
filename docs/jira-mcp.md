# Ponte inicial Jira MCP (histórico)

Este documento registra a integração anterior. A CLI ativa consulta Jira por REST GET com `adapters/jira/get-issue.ps1`; consulte [architecture-v2.md](architecture-v2.md). A ponte MCP legada permanece no repositório para não afetar consumidores antigos, mas não é usada pelo novo fluxo.

O Workspace Core lê o chamado pelo Jira MCP já configurado em `C:\htdocs\squad-ia\tools\mcp\jira.ps1`. O adaptador `adapters/jira/mcp_client.py` inicia esse processo isoladamente, chama somente `jira_get_issue` com `update_history=false`, solicita resumo, status e atualização, normaliza a resposta e envia os metadados ao Core pela entrada padrão. Não armazena tokens, descrição, comentários ou anexos, não publica no Jira e não modifica o OpenSquad. O launcher existente usa a credencial local fora deste repositório.

O servidor Jira não constava em `codex mcp list --json` neste terminal; a chamada isolada ao launcher existente foi testada com sucesso. O adaptador é específico para `evolog.atlassian.net`.

## Fluxo testado

Na raiz do monorepositório, com PostgreSQL conectado:

```powershell
python adapters/jira/mcp_client.py --import-issue EVOLOG-31599 --project webagil
```

A primeira execução retornou `updated` para o ticket já cadastrado, ID `13de93e6-a823-4ec5-8b18-de84af8c471e`. A segunda retornou `unchanged` com o mesmo ID. Em novo processo, a rota de histórico retornou HTTP 200, uma run, cinco artefatos e os metadados Jira preenchidos. O MCP retornou a atualização como horário local com o sufixo `Hora oficial do Brasil`; o adaptador usou a base de fusos do PHP para convertê-la para ISO 8601 com `America/Sao_Paulo`.

## Contrato de entrada

Para integrar outra ferramenta MCP ou importar um snapshot revisado manualmente, confira o site, a chave e o ID da issue no resultado real. Salve apenas os campos abaixo em JSON UTF-8, fora do repositório, por exemplo em uma pasta temporária protegida:

```json
{
  "site": "evolog.atlassian.net",
  "key": "EVOLOG-12345",
  "issue_id": "123456",
  "summary": "Resumo retornado pelo Jira",
  "status": "Em andamento",
  "updated_at": "2026-11-13T10:00:00Z"
}
```

O exemplo é ilustrativo. Não use esses valores como evidência de um chamado real. O importador aceita somente essas seis propriedades, exige que `site` e `key` coincidam com os argumentos, limita o arquivo a 1 MiB e recusa links simbólicos. Descrição, comentários, anexos e credenciais não entram no banco nesta etapa.

## Importação

No diretório `apps/control-api`, depois de `php artisan migrate`:

```powershell
php -d xdebug.mode=off artisan workspace:import-jira-mcp webagil evolog.atlassian.net EVOLOG-12345 --file="C:\caminho\temporario\jira.json"
```

O projeto precisa existir. Uma chave Jira já cadastrada mantém seu UUID e suas runs. Repetir o mesmo snapshot retorna `unchanged`; uma versão mais nova atualiza resumo, status e horário da issue. O comando recusa mudança de projeto, troca do ID externo e snapshot anterior à versão armazenada. `GET /api/tickets/{id}/history` e `scripts/windows/history.ps1` retornam os metadados com o histórico já vinculado. O adaptador automático usa `--stdin`, sem arquivo intermediário.

O arquivo JSON de transporte pode conter dados internos. Mantenha-o fora do repositório, controle o acesso e remova-o conforme a política local depois da importação. O comando não altera o arquivo de entrada.

## Limite de validação

A migration PostgreSQL `2026_11_13_000003_add_jira_ticket_snapshot` executou. Os testes automatizados exercitaram criação, atualização de ticket existente, repetição e rejeições com um snapshot controlado: 4 testes e 53 asserções. A leitura real e a importação repetida de `EVOLOG-31599` também passaram. Nenhuma configuração global do Maestri ou dos executores foi alterada.
