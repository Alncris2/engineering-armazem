# Catálogo de projetos

O catálogo é persistido no PostgreSQL. `config/projects/catalog.json` contém os dados declarados para a sincronização inicial, sem credenciais. A migration `2026_11_13_000002_add_project_catalog` acrescenta descrição aos projetos, unicidade de caminho por projeto e a tabela `repository_technologies`, ligada a `repositories` por chave estrangeira.

## API

- `PATCH /api/projects/{id}`: atualiza `description`.
- `GET /api/projects/{id}`: retorna o projeto, seus repositórios e as tecnologias de cada um.
- `GET /api/projects/{id}/repositories`: lista os repositórios com tecnologias.
- `POST /api/projects/{id}/repositories`: recebe `name`, caminho absoluto Windows em `path` e `role` (`backend`, `frontend`, `fullstack`, `shared`). Repetir os mesmos dados retorna o registro existente; conflito de nome ou caminho retorna 409.
- `POST /api/repositories/{id}/technologies`: recebe `name`, `role` (`runtime`, `framework`, `database`), `declared_version` opcional, `observed_version` opcional e `observed_source` obrigatório quando há versão observada. Repetir os mesmos dados retorna o registro existente; divergência retorna 409.

Para preencher os seis projetos existentes: inicie a API em loopback e execute `pwsh -NoProfile -File scripts/windows/sync-project-catalog.ps1`. O script verifica se os projetos e diretórios existem antes de gravar e pode ser repetido. Para consultar em uma sessão nova: `pwsh -NoProfile -File scripts/windows/project.ps1 -Slug fastapi`.

## Declaração e observação

As versões declaradas pelo usuário ficam em `declared_version`. Quando um manifest local forneceu outra versão, `observed_version` e `observed_source` preservam essa evidência. Em `fastapi`, Python 3.7.4 foi declarado, mas `.python-version` contém 3.10.8. `Agend Node` foi interpretado como Node.js porque o repositório tem `package.json`; nenhuma versão de Node foi inferida. Para Server, a versão Node.js 14 é declarada e não foi verificada por `engines` no manifest. A versão Angular 10.1.2 veio de `package.json` nos três frontends; Laravel 13.30.0 veio de `composer.json` do Webagil.

O mesmo diretório `C:\htdocs\server` aparece nos projetos Server, Warehouse e LMS como vínculo próprio de cada projeto. O catálogo guarda caminhos e metadados, não copia nem modifica arquivos nesses repositórios.
