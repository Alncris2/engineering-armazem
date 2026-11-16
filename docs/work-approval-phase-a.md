# Aprovação de work: fase A simulada

Esta fase define um contrato e permite exercitar `request`, `status` e `consume` **somente com mock**. O mock é público, determinístico e falsificável. Seus recibos têm `usable_for_real_work: false`; não há conexão desse serviço com a retomada do LangGraph. `work` e `review` reais continuam retornando `CODEX_STAGE_DISABLED` na root CLI e na CLI de desenvolvimento. Nenhuma aprovação WebAuthn foi registrada ou verificada.

## Contrato v1

`services/orchestrator/development/approval_contract.py` serializa JSON UTF-8 com chaves ordenadas, sem espaços e sem NaN, e calcula SHA-256 desses bytes. O envelope fechado contém: `version=1`, `thread_id` novo, `issue_key`, `stage=work`, `attempt=1`, `plan_sha256`, `spec_sha256`, `repo`, `head`, `inventory_sha256`, `allowlist`, `target_module`, `nonce`, `issued_at`, `expires_at`. `repo` deve ser o caminho Windows canônico `C:\htdocs\ai-engineering-workspace\tmp\development-sandboxes\<thread>\example-repo`; a allowlist contém apenas o módulo alvo. Nonce aleatório de 256 bits; validade padrão 120 s e máxima 300 s, em UTC. O request mock rejeita campos extras, hashes inválidos e troca de estágio, tentativa, repositório ou alvo.

A validação exige `version` inteiro (booleano não vale como 1) e correspondência exata do caminho canônico, inclusive maiúsculas e minúsculas.

O SHA da spec vincula bytes, mas **não prova** que a spec esteja sem Open Questions. O futuro gate real precisará ler a spec, aplicar `check_spec_open_questions`, confirmar o SHA, o plano, a thread nova, o HEAD e o inventário observados imediatamente antes de work. O próprio envelope não substitui essa verificação.

## Persistência

A migration `2026_11_13_000005_create_work_approval_contract.php` define tabelas de credenciais, challenges e aprovações para implantação futura. Há chaves únicas para nonce, digest do payload e `(thread_id, stage, attempt)`, FK de aprovação para challenge/credencial, índices de expiração e checks PostgreSQL para versão, estágio, estado, tamanho de hash e prazo máximo. O check de `work_approvals` **proíbe `verifier_kind=mock`** e exige credencial/assertion para decisão aprovada. **A migration não foi aplicada ao PostgreSQL conectado.** A execução de teste usa SQLite `:memory:`; os checks específicos do PostgreSQL ainda não foram exercitados em um banco isolado. A migration não concede privilégios nem torna o banco atual confiável; na fase B o papel do orquestrador deve perder escrita direta nessas tabelas.

O mock usa SQLite separado sob `tmp/approval-mock` e `BEGIN IMMEDIATE`. O consumo confere bytes canônicos, digest, prova mock, estado pendente e expiração dentro da mesma transação; atualiza o challenge e insere uma única aprovação. Exceção antes do commit reverte ambos. Erro do banco, lock, replay, campo trocado ou expiração negam o consumo. `status` é apenas observação, nunca autorização.

O consumo usa um único instante UTC, obtido sob o lock da transação, para conferir a validade e registrar `consumed_at`.

## Verificação da fase A

Em 13/11/2026, a suíte Python da raiz passou com 8 testes; a suíte `tests/development` passou com 53 testes (51 executados e 2 ignorados por dependerem de `DEVELOPMENT_CHECKPOINT_DSN`), incluindo 10 testes de `test_approval_mock.py`; o PHPUnit passou com 4 testes e 56 asserções. `php -l` da migration passou. O teste da migration executou apenas em SQLite `:memory:`; a migration e seus checks PostgreSQL não foram executados no PostgreSQL pessoal. As suítes Python foram executadas sem DSN de checkpoint.

Os testes de CLI recusam `work` e `review` reais com `CODEX_STAGE_DISABLED`. Isso confirma o bloqueio nas entradas exercitadas; não constitui aprovação humana ou verificação WebAuthn. O mock continua sem ligação com a retomada do grafo.

Para a fase futura, os constraints PostgreSQL validam apenas formato e presença. Eles não provam assinatura WebAuthn, presença/verificação do usuário (UV), igualdade entre `work_approvals.payload_sha256` e o challenge correspondente, nem que o challenge esteja consumido. Um verificador independente deverá comprovar esses fatos e vincular o atestado ao contexto observado. A reivindicação do challenge deverá ser transacional, com `SELECT FOR UPDATE` ou `UPDATE` condicional, e ocorrer por papel de banco separado, sem escrita direta do orquestrador. Os testes desses constraints exigem banco PostgreSQL descartável e isolado. O `down()` da migration derruba as tabelas e seus dados; não executar rollback no banco pessoal.

## CLI local de simulação

No PowerShell, a partir de `services/orchestrator`, com entrada JSON contendo os campos de request acima, sem `version`, `nonce` ou timestamps:

```powershell
.\.venv-workspace\Scripts\python.exe -m development.approval_mock request --mode mock --db C:\htdocs\ai-engineering-workspace\tmp\approval-mock\exemplo.sqlite3 --input C:\caminho\request.json
.\.venv-workspace\Scripts\python.exe -m development.approval_mock status --mode mock --db C:\htdocs\ai-engineering-workspace\tmp\approval-mock\exemplo.sqlite3 --nonce <nonce>
.\.venv-workspace\Scripts\python.exe -m development.approval_mock consume --mode mock --db C:\htdocs\ai-engineering-workspace\tmp\approval-mock\exemplo.sqlite3 --input C:\caminho\payload.json --proof <mock_proof>
```

O `request` devolve o payload completo e uma prova mock, calculável por qualquer processo. Isso serve apenas para testes do contrato e da máquina de estados. Não use a prova como evidência de presença humana, nem conceda work com `verifier_kind=mock`.

## Fase B necessária antes de segurança real

Provisionar um verificador fora da raiz gravável e sob outra conta/serviço Windows; proteger código, credenciais e IPC por ACL; separar papéis PostgreSQL, removendo acesso de escrita do orquestrador às aprovações e aos checkpoints que governam o gate; vincular o atestado assinado ao challenge e à operação observada; registrar credencial por fluxo confiável e só então integrar WebAuthn. Com o mesmo SID e a conexão PostgreSQL superusuária atual, o agente poderia contornar um gate implementado apenas em código ou banco local.
