# Fase B: SQL proposto para revisão

**Preparado; nenhum bloco abaixo foi executado.** Os nomes de role e o banco de exemplo são propostos. Os blocos de transação usam parâmetros `%s` do psycopg, não interpolação de strings nem comandos prontos para `psql`. Executar somente após revisão em PostgreSQL descartável isolado. A migration Laravel `000005` não foi aplicada ao PostgreSQL pessoal. O SQL não prova WebAuthn: essa verificação criptográfica pertence ao serviço protegido.

## Delta da migration `000005`

Aplicar `000005` primeiro **em banco vazio de ensaio**, depois criar migration aditiva revisada. `000005` usa tabelas no schema `public`, UUIDs fornecidos pela aplicação, JSON para payload, `timestampTz`, `stage='work'` e `attempt=1`. O delta proposto exige bytes canônicos, evidência WebAuthn mínima e ledger de atestado/claim. O bloco com `ADD COLUMN ... NOT NULL` abaixo **só é válido se as três tabelas de `000005` estiverem vazias**, comprovado dentro da mesma janela de manutenção e sem escritores concorrentes. Em banco preexistente, planejar migração expand/backfill/validate/set-not-null por campo; não reconstruir bytes canônicos a partir de JSON. Não executar `down()` de `000005` para desfazer o ensaio; ele elimina os dados. Rollback operacional desabilita gate e preserva ledger.

```sql
BEGIN;
ALTER TABLE public.work_approval_credentials
  ADD COLUMN actor_id text NOT NULL,
  ADD COLUMN registration_evidence_sha256 varchar(64) NOT NULL,
  ADD COLUMN registered_origin text NOT NULL,
  ADD COLUMN registered_user_handle bytea NOT NULL,
  ADD COLUMN user_handle_policy text NOT NULL
    CHECK (user_handle_policy IN ('required','allow_absent_nondiscoverable')),
  ADD COLUMN counter_policy text NOT NULL
    CHECK (counter_policy IN ('monotonic','unsupported'));
ALTER TABLE public.work_approval_challenges
  ADD COLUMN payload_canonical bytea NOT NULL;
ALTER TABLE public.work_approval_challenges
  ADD CONSTRAINT work_challenge_id_digest_unique UNIQUE (id, payload_sha256);
ALTER TABLE public.work_approvals
  ADD CONSTRAINT work_approval_same_payload_fk
  FOREIGN KEY (challenge_id, payload_sha256)
  REFERENCES public.work_approval_challenges (id, payload_sha256);

CREATE TABLE public.work_approval_attestations (
  id uuid PRIMARY KEY,
  approval_id uuid NOT NULL UNIQUE REFERENCES public.work_approvals(id),
  key_id text NOT NULL,
  algorithm text NOT NULL CHECK (algorithm = 'ES256'),
  signed_payload bytea NOT NULL,
  signature bytea NOT NULL,
  issued_at timestamptz NOT NULL
);
CREATE TABLE public.work_approval_webauthn_evidence (
  approval_id uuid PRIMARY KEY REFERENCES public.work_approvals(id),
  client_data_json bytea NOT NULL,
  authenticator_data bytea NOT NULL,
  signature bytea NOT NULL,
  credential_id_raw bytea NOT NULL,
  user_handle bytea,
  credential_id_sha256 varchar(64) NOT NULL,
  captured_at timestamptz NOT NULL,
  retain_until timestamptz NOT NULL,
  CHECK (length(credential_id_raw) > 0 AND length(client_data_json) > 0
         AND length(authenticator_data) > 0 AND length(signature) > 0
         AND (user_handle IS NULL OR length(user_handle) > 0)
         AND credential_id_sha256 ~ '^[0-9a-f]{64}$'),
  CHECK (retain_until > captured_at)
);
CREATE TABLE public.work_approval_launch_claims (
  id uuid PRIMARY KEY,
  approval_id uuid NOT NULL UNIQUE REFERENCES public.work_approvals(id),
  operation_key text NOT NULL UNIQUE,
  state text NOT NULL CHECK (state IN ('reserved','launching','unknown','completed','aborted')),
  reserved_at timestamptz NOT NULL,
  launching_at timestamptz,
  completed_at timestamptz,
  snapshot_sha256 varchar(64),
  snapshot_location_id text,
  CHECK ((state = 'reserved' AND launching_at IS NULL AND completed_at IS NULL
          AND snapshot_sha256 IS NULL AND snapshot_location_id IS NULL)
      OR (state IN ('launching','unknown') AND launching_at IS NOT NULL
          AND launching_at >= reserved_at AND completed_at IS NULL
          AND snapshot_sha256 IS NOT NULL AND snapshot_sha256 ~ '^[0-9a-f]{64}$'
          AND snapshot_location_id IS NOT NULL
          AND snapshot_location_id ~ '^[A-Za-z0-9_-]{1,128}$')
      OR (state IN ('completed','aborted') AND launching_at IS NOT NULL
          AND launching_at >= reserved_at AND completed_at IS NOT NULL
          AND completed_at >= launching_at AND snapshot_sha256 IS NOT NULL
          AND snapshot_sha256 ~ '^[0-9a-f]{64}$'
          AND snapshot_location_id IS NOT NULL
          AND snapshot_location_id ~ '^[A-Za-z0-9_-]{1,128}$'))
);
-- A CHECK valida cada linha; o trigger abaixo valida a transição entre linhas.
CREATE FUNCTION public.ws_approval_claim_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.state <> 'reserved' THEN
      RAISE EXCEPTION 'claim must start reserved';
    END IF;
    NEW.reserved_at := clock_timestamp();
    RETURN NEW;
  END IF;
  IF NEW.id IS DISTINCT FROM OLD.id
     OR NEW.approval_id IS DISTINCT FROM OLD.approval_id
     OR NEW.operation_key IS DISTINCT FROM OLD.operation_key
     OR NEW.reserved_at IS DISTINCT FROM OLD.reserved_at THEN
    RAISE EXCEPTION 'claim identity is immutable';
  END IF;
  IF NOT ((OLD.state = 'reserved' AND NEW.state = 'launching')
       OR (OLD.state = 'launching' AND NEW.state IN ('unknown','completed'))
       OR (OLD.state = 'unknown' AND NEW.state IN ('completed','aborted'))) THEN
    RAISE EXCEPTION 'invalid claim transition';
  END IF;
  IF OLD.state <> 'reserved' AND
     (NEW.snapshot_sha256 IS DISTINCT FROM OLD.snapshot_sha256
      OR NEW.snapshot_location_id IS DISTINCT FROM OLD.snapshot_location_id
      OR NEW.launching_at IS DISTINCT FROM OLD.launching_at) THEN
    RAISE EXCEPTION 'launch snapshot is immutable';
  END IF;
  IF OLD.state = 'reserved' THEN
    NEW.launching_at := clock_timestamp();
  ELSIF NEW.state IN ('completed','aborted') THEN
    NEW.completed_at := clock_timestamp();
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.ws_approval_claim_guard() FROM PUBLIC;
CREATE TRIGGER ws_approval_claim_guard_before
  BEFORE INSERT OR UPDATE ON public.work_approval_launch_claims
  FOR EACH ROW EXECUTE FUNCTION public.ws_approval_claim_guard();
COMMIT;
```

Se houver rows prévias, `ADD COLUMN ... NOT NULL` falha: não fazer backfill automático de payload canônico a partir de `json`, porque a reserialização pode alterar os bytes assinados. Quarentenar e decidir migração manualmente. O FK composto garante igualdade do hash aprovação/challenge, mas não prova bytes corretos, assinatura, UV ou `state='consumed'`. O serviço verifica esses pontos e o UPDATE condicional os vincula na transação.

`registration_evidence_sha256` aponta para evidência de bootstrap guardada fora do workspace sob ACL do serviço; não é prova por si só. `actor_id`, `registered_user_handle` e `user_handle_policy` vêm do cadastro humano validado. O serviço valida que `id` textual da assertion, se presente, decodifica em exatamente `rawId`, guarda os bytes de `rawId` em `credential_id_raw` e compara seu SHA-256 ao ID cadastrado. Se a assertion trouxer `userHandle`, compara bytes exatos com `registered_user_handle`; se vier ausente, aceita só quando `user_handle_policy='allow_absent_nondiscoverable'`, mantendo a ausência no ledger. `counter_policy='unsupported'` exige auditoria específica do autenticador, não regra genérica de aceitar regressão. `credential_id_raw`, `user_handle`, `client_data_json`, `authenticator_data` e `signature` são os bytes exatos recebidos e verificados; o hash isolado não permite auditoria independente. Manter acesso somente de verificador e auditor designado, cifra em repouso e backup protegido, log de leitura, retenção definida pela política local e descarte auditado **após** prazo e ausência de legal hold. O exemplo não implementa job de descarte nem escolhe prazo legal; sem política aprovada, não implantar.

Framing **exato** de `work_approvals.assertion_sha256`: `SHA256` dos bytes `ASCII("WS-WEBAUTHN-ASSERTION-V1") || 0x00 || field(credential_id_raw) || field(user_handle) || field(client_data_json) || field(authenticator_data) || field(signature)`, nessa ordem. `field(x)` é um byte de presença (`0x00` para ausente, `0x01` para presente), seguido de comprimento unsigned de 32 bits em big-endian e bytes brutos; para ausente, comprimento zero e nenhum byte. Os quatro campos obrigatórios usam presença `0x01`, `user_handle` ausente usa `0x00`; `0x01` com comprimento zero é distinto de ausência e deve ser rejeitado quando inválido para o campo. Limitar tamanho de cada campo antes de alocar/hashear e rejeitar comprimento acima de `2^32-1`. Não base64, reserializar JSON nem usar separador textual. O serviço recomputa o hash sobre os bytes persistidos, confere `SHA256(credential_id_raw)=credential_id_sha256` da evidência e da credencial ativa, `user_handle` contra registro/política, e vincula o hash ao atestado assinado. Teste de vetor fixo e mudança de um byte/presença são obrigatórios no ensaio.

Para cumprir a recomputação a partir do ledger, **depois do INSERT** o verificador lê pelo `approval_id` somente as sete colunas concedidas abaixo, remonta o framing a partir desses bytes retornados e compara com `work_approvals.assertion_sha256` antes do COMMIT. Zero ou múltiplas linhas, leitura negada ou digest diferente causam ROLLBACK. O grant é de colunas, não de tabela inteira: não inclui `captured_at` nem `retain_until`, e não concede leitura a agente, checkpoint, enroller ou broker. Ele ainda permite ao verificador ler essas colunas em outras linhas; essa capacidade fica limitada ao SID/DSN do serviço protegido, com auditoria de acesso e retenção. Auditoria independente futura usa credencial de auditor separada, protegida e provisionada offline, sujeita a revisão própria; não ampliar os grants de runtime para suprir esse caso.

O trigger é somente modelo de migration **offline** sob owner protegido; além de `REVOKE EXECUTE`, conferir ownership da função/trigger, `CREATE` e `search_path` para impedir substituição. Os grants de UPDATE de coluna não impõem transições. A função restringe `reserved -> launching -> unknown/completed` e `unknown -> completed/aborted`; `completed`/`aborted` são terminais. Não existe `unknown -> launching` nem cancelamento silencioso de `reserved`. `CHECK` exige hash minúsculo hex de 64 caracteres, location ID opaco não vazio, presença de snapshot após o lançamento e timestamps ordenados; o trigger fixa `reserved_at`, `launching_at` e `completed_at` no relógio do banco e congela hash, location e `launching_at` a partir de `launching`. O broker não recebe owner/DDL; DBA e dono do banco permanecem na base de confiança. Testar tudo em PG18 isolado antes de adaptar ao banco real.

## Roles e ownership propostos

O bloco é **modelo para banco descartável**, não script de produção. `workspace_disposable` é ilustrativo; credenciais ficam fora do repo. Ordem obrigatória:

1. Com DBA autorizado, inventariar roles e memberships diretas/indiretas (`pg_roles`, `pg_auth_members` com opções `inherit_option`/`set_option`), owners de tabelas, sequences, schemas e funções, grants explícitos/default/PUBLIC, `has_*_privilege`, `search_path` de banco/roles/sessão e `CREATE` em todos os schemas do path. Inventariar tabelas **já existentes** do PostgresSaver e suas migrations/versionamento; não assumir banco vazio nem chamar `setup()` no runtime.
2. Em ensaio descartável, DBA cria roles `NOLOGIN` de owner e roles LOGIN sem herança de owner. Executar `000005`, delta e `PostgresSaver.setup()` **offline**, com DSN de migração protegido, antes da transferência de ownership; verificar versão real do pacote e DDL criado. O instalador offline usa role de bootstrap com privilégios suficientes, jamais DSN herdado pelo agente. Para migrar instância existente, parar escritores e conferir linhas/grants/owners antes de qualquer DDL.
3. Transferir ownership com superuser DBA **ou** com owner atual que tenha capacidade comprovada de `SET ROLE` para o novo owner e `CREATE` no schema de destino; em PostgreSQL 18, conferir explicitamente as opções de membership. `ALTER OWNER` não é operação concedida por simples `GRANT ALL` na tabela. Se a condição não existir, parar; não dar membership de owner nem `CREATE` ao runtime para contornar erro. Considerar schemas dedicados em implantação real; se manter `public`, revogar `CREATE` de `PUBLIC` e testar impacto em outro software antes.
4. Conceder apenas DML preciso, revogar grants legados e **testar com login real de cada DSN** e `SET ROLE` negativo; `SET ROLE` do DBA de ensaio pode mascarar memberships e credenciais reais. Só depois remover DSN superuser de `workspace.py`/config Laravel e da herança de ambiente de `development.cli` e `workflow.py`, usar DSNs separados para aplicação, checkpoint, verificador e broker, e remover os dois `saver.setup()` do runtime. Falha no upgrade offline deve impedir inicialização, nunca tentar DDL no processo de runtime.

`REVOKE` abaixo não neutraliza owner, membership privilegiada, superuser, grant herdado por outra role, `CREATE` no schema ou `search_path` com schema gravável. `NOBYPASSRLS` **não habilita RLS**; este desenho usa isolamento por ownership/grants, e qualquer política RLS futura exige `ENABLE/FORCE ROW LEVEL SECURITY` e testes próprios. Reavaliar grants de aplicação e default privileges no banco real antes de adaptar o exemplo.

```sql
BEGIN;
CREATE ROLE ws_approval_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE ws_checkpoint_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE ws_approval_verifier LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE ws_approval_enroller LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE ws_approval_broker LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE ws_checkpoint_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

ALTER TABLE public.work_approval_credentials OWNER TO ws_approval_owner;
ALTER TABLE public.work_approval_challenges OWNER TO ws_approval_owner;
ALTER TABLE public.work_approvals OWNER TO ws_approval_owner;
ALTER TABLE public.work_approval_attestations OWNER TO ws_approval_owner;
ALTER TABLE public.work_approval_webauthn_evidence OWNER TO ws_approval_owner;
ALTER TABLE public.work_approval_launch_claims OWNER TO ws_approval_owner;
ALTER FUNCTION public.ws_approval_claim_guard() OWNER TO ws_approval_owner;
ALTER TABLE public.checkpoints OWNER TO ws_checkpoint_owner;
ALTER TABLE public.checkpoint_blobs OWNER TO ws_checkpoint_owner;
ALTER TABLE public.checkpoint_writes OWNER TO ws_checkpoint_owner;
ALTER TABLE public.checkpoint_migrations OWNER TO ws_checkpoint_owner;

REVOKE ALL ON TABLE public.work_approval_credentials,
  public.work_approval_challenges, public.work_approvals,
  public.work_approval_attestations, public.work_approval_webauthn_evidence,
  public.work_approval_launch_claims
  FROM PUBLIC, ws_checkpoint_runtime;
REVOKE ALL ON TABLE public.checkpoints, public.checkpoint_blobs,
  public.checkpoint_writes, public.checkpoint_migrations
  FROM PUBLIC, ws_approval_verifier, ws_approval_enroller, ws_approval_broker;

GRANT USAGE ON SCHEMA public TO ws_approval_verifier, ws_approval_enroller,
  ws_approval_broker, ws_checkpoint_runtime;
GRANT CONNECT ON DATABASE workspace_disposable
  TO ws_approval_verifier, ws_approval_enroller,
     ws_approval_broker, ws_checkpoint_runtime;

GRANT SELECT ON public.work_approval_credentials,
  public.work_approval_challenges, public.work_approvals,
  public.work_approval_attestations, public.work_approval_launch_claims
  TO ws_approval_verifier;
GRANT INSERT ON public.work_approval_challenges, public.work_approvals,
  public.work_approval_attestations, public.work_approval_webauthn_evidence,
  public.work_approval_launch_claims
  TO ws_approval_verifier;
GRANT SELECT (approval_id, credential_id_raw, user_handle, client_data_json,
              authenticator_data, signature, credential_id_sha256)
  ON public.work_approval_webauthn_evidence TO ws_approval_verifier;
GRANT UPDATE (state, consumed_at, updated_at)
  ON public.work_approval_challenges TO ws_approval_verifier;
GRANT UPDATE (sign_count, updated_at)
  ON public.work_approval_credentials TO ws_approval_verifier;
GRANT SELECT ON public.work_approval_challenges, public.work_approvals,
  public.work_approval_attestations, public.work_approval_launch_claims
  TO ws_approval_broker;
GRANT UPDATE (state, launching_at, completed_at, snapshot_sha256, snapshot_location_id)
  ON public.work_approval_launch_claims TO ws_approval_broker;

GRANT SELECT, INSERT ON public.work_approval_credentials TO ws_approval_enroller;
GRANT UPDATE (state, registered_at, revoked_at, updated_at)
  ON public.work_approval_credentials TO ws_approval_enroller;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON public.checkpoints, public.checkpoint_blobs, public.checkpoint_writes
  TO ws_checkpoint_runtime;
GRANT SELECT ON public.checkpoint_migrations TO ws_checkpoint_runtime;
COMMIT;
```

`ws_approval_enroller` é papel de operação humana temporária para bootstrap/revogação; sua credencial não vai ao serviço de runtime. `ws_checkpoint_runtime` é do orquestrador e pode alterar **seus checkpoints**, que por isso não autorizam nada. `ws_approval_verifier` é exclusivo do serviço, insere reserva `reserved` mas não atualiza claim; `ws_approval_broker` é exclusivo do broker sob SID separado e não pode inserir reservas, consumir challenge ou criar aprovação. Ambos ficam inacessíveis ao processo do agente. O owner sem login e o papel de migração offline ficam fora do runtime. O bloco de grants é demonstrativo: antes de uso real, auditar privilégios herdados/default/PUBLIC e revogar explicitamente qualquer excesso. O trigger é `SECURITY INVOKER`, não `SECURITY DEFINER`; qualquer função futura com definidor privilegiado exige revisão específica de owner, `search_path` e `EXECUTE`. Nenhuma role runtime recebe `CREATE` em schema, ownership, `SET ROLE` para owner ou superuser. Remover `saver.setup()` de **ambas** as CLIs de execução normal: só papel de migração offline pode mudar schema do PostgresSaver.

## Transação de emissão

O serviço valida request e bytes antes de abrir a transação. Todos os placeholders vêm de valores validados, com bind do psycopg. UUIDs são gerados pelo serviço. `payload_canonical` contém exatamente o UTF-8 produzido por `canonical_bytes`; `%s::json` recebe esse mesmo texto. A operação só responde após COMMIT. Violação de UNIQUE gera negação, sem novo nonce para a mesma thread.

```sql
BEGIN ISOLATION LEVEL READ COMMITTED;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '5s';
INSERT INTO public.work_approval_challenges
  (id, contract_version, thread_id, issue_key, stage, attempt,
   plan_sha256, spec_sha256, repo, head, inventory_sha256, allowlist,
   target_module, nonce, payload_sha256, payload, payload_canonical,
   state, issued_at, expires_at, created_at, updated_at)
VALUES
  (%s::uuid, 1, %s, %s, 'work', 1,
   %s, %s, %s, %s, %s, %s::json,
   %s, %s, %s, %s::json, %s::bytea,
   'pending', %s::timestamptz, %s::timestamptz,
   clock_timestamp(), clock_timestamp())
RETURNING id;
COMMIT;
```

O serviço confere que `SHA256(payload_canonical)=payload_sha256`, prazo `issued_at < expires_at <= issued_at+300s`, `nonce` 32 bytes, `stage=work`, `attempt=1`, thread nova e spec sem Open Questions. Os constraints `000005` só conferem parte disso. Não usar `ON CONFLICT DO UPDATE` para reabrir challenge.

## Transação de consumo único

Antes da transação, o serviço lê challenge/credencial sem lock em conexão de leitura, compara bytes canônicos, recomputa hashes, reobserva repo/HEAD/spec/plano/inventário/allowlist/alvo e verifica WebAuthn, inclusive `credential_id_raw` e `user_handle`; nenhuma dessas leituras autoriza consumo. Impõe deadline monotônico total de 6 s para a operação e cancela ao estourar. Só então usa **uma conexão dedicada e uma transação curta** para `SELECT FOR UPDATE`, refaz comparação dos campos/versões, contador, estado e digest do contexto observado e executa DML; se a revalidação de arquivos não couber no orçamento, falha fechado. Não manter lock durante varredura longa de arquivos ou criptografia WebAuthn. O contexto de arquivos precisa estar protegido por snapshot/ACL para a comparação curta ser suficiente; sem isso, TOCTOU continua NO-GO. O atestado ES256, assinado sob o mesmo deadline, cobre (`domain=workspace-work-approval-v1`, challenge ID, payload SHA, operation key, hash do ID da credencial, assertion SHA, instante de consumo, decisão, versão do verificador); guarda os bytes exatos assinados. Não assinar JSON reserializado pelo banco. `clock_timestamp()` **no UPDATE condicional após a verificação** impede consumir depois do prazo. Qualquer divergência, zero rows, timeout ou erro implica ROLLBACK e negação.

Em PG18, aplicar na **conexão dedicada**, antes de `BEGIN`, `transaction_timeout=8s`, `idle_in_transaction_session_timeout=3s`, `statement_timeout=5s` e `lock_timeout=2s`; esses valores são ilustrativos e devem ser medidos no ensaio. `transaction_timeout` cobre intervalos entre statements; `statement_timeout` sozinho não cobre Python parado com locks. O cliente usa deadline monotônico de 6 s, `try/finally` com rollback explícito se ainda houver transação e fecha/descarta a conexão após timeout ou erro de conexão, inclusive quando o servidor encerra a sessão. O serviço só responde sucesso após confirmação de COMMIT; se o COMMIT ficar ambíguo, consulta o ledger em nova conexão e **não reexecuta** o consumo. Não alterar `postgresql.conf` nem configuração global.

```sql
-- SETs de sessão na conexão dedicada, antes de BEGIN; fechar/resetar ao terminar.
SET transaction_timeout = '8s';
SET idle_in_transaction_session_timeout = '3s';
SET statement_timeout = '5s';
SET lock_timeout = '2s';
BEGIN ISOLATION LEVEL READ COMMITTED;

SELECT id, payload_canonical, payload_sha256, state, issued_at, expires_at,
       thread_id, issue_key, stage, attempt, plan_sha256, spec_sha256,
       repo, head, inventory_sha256, target_module
  FROM public.work_approval_challenges
 WHERE nonce = %s
 FOR UPDATE;

SELECT id, public_key, rp_id, actor_id, registered_origin, registered_user_handle,
       user_handle_policy,
       counter_policy, sign_count, state, revoked_at
  FROM public.work_approval_credentials
 WHERE credential_id_sha256 = %s
 FOR UPDATE;

-- Revalidar rapidamente campos/versões/digests/contexto contra a verificação
-- feita fora da transação, credencial ativa, contador, ID e userHandle.
-- Se qualquer dado mudou ou deadline estourou: ROLLBACK, sem DML.

-- O instante definitivo é avaliado uma vez aqui, depois da verificação.
-- CTE evita timestamps distintos entre predicado e consumed_at.
WITH instant AS MATERIALIZED (SELECT clock_timestamp() AS t)
UPDATE public.work_approval_challenges
   SET state = 'consumed', consumed_at = instant.t,
       updated_at = instant.t
  FROM instant
 WHERE id = %s::uuid AND state = 'pending'
   AND issued_at <= instant.t AND expires_at > instant.t
   AND payload_sha256 = %s
 RETURNING public.work_approval_challenges.id,
           public.work_approval_challenges.consumed_at;
-- Exigir exatamente uma linha; caso contrário ROLLBACK.

UPDATE public.work_approval_credentials
   SET sign_count = %s, updated_at = clock_timestamp()
 WHERE id = %s::uuid AND state = 'active' AND revoked_at IS NULL
   AND sign_count = %s
 RETURNING id;
-- Exigir exatamente uma linha; política explícita para contador zero.

INSERT INTO public.work_approvals
  (id, challenge_id, credential_id, decision, verifier_kind,
   payload_sha256, assertion_sha256, decided_at, created_at, updated_at)
VALUES
  (%s::uuid, %s::uuid, %s::uuid, 'approved', 'webauthn',
   %s, %s, %s::timestamptz, clock_timestamp(), clock_timestamp())
RETURNING id;

INSERT INTO public.work_approval_webauthn_evidence
  (approval_id, client_data_json, authenticator_data, signature,
   credential_id_raw, user_handle, credential_id_sha256, captured_at, retain_until)
VALUES (%s::uuid, %s::bytea, %s::bytea, %s::bytea,
        %s::bytea, %s::bytea, %s, %s::timestamptz, %s::timestamptz);
-- Parâmetros são bytes exatos e timestamp/retention aprovados; nenhuma cópia no checkpoint.
SELECT approval_id, credential_id_raw, user_handle, client_data_json,
       authenticator_data, signature, credential_id_sha256
  FROM public.work_approval_webauthn_evidence
 WHERE approval_id = %s::uuid;
-- Exigir exatamente uma linha. Recomputar assertion_sha256 dos bytes retornados,
-- comparar com o approval e abortar antes do COMMIT em caso de divergência.

INSERT INTO public.work_approval_attestations
  (id, approval_id, key_id, algorithm, signed_payload, signature, issued_at)
VALUES (%s::uuid, %s::uuid, %s, 'ES256', %s::bytea, %s::bytea, %s::timestamptz);

INSERT INTO public.work_approval_launch_claims
  (id, approval_id, operation_key, state, reserved_at)
VALUES (%s::uuid, %s::uuid, %s, 'reserved', %s::timestamptz);
COMMIT;
```

`operation_key` é exatamente `thread_id:work:1`, com UNIQUE. O serviço não libera bearer token de launch ao orquestrador. O broker futuro recebe solicitação apenas pela interface privada autenticada pelo SID do broker e por binding de sessão/nonce; o agente não possui acesso a essa interface, DSN ou identidade. O broker lê a reserva diretamente, reobserva repo/HEAD/spec/plano/inventário/allowlist/alvo, congela snapshot sob ACL que exclui o agente, confere seu hash e executa, sob sua role, transição condicional `reserved -> launching` que preenche `snapshot_sha256` e `snapshot_location_id`; o trigger fixa `launching_at=clock_timestamp()`. Exige exatamente uma linha, commit durável e nova conferência do snapshot antes do spawn; nunca executa sobre repo vivo. Falha entre commit e spawn é **unknown** até reconciliação manual; nunca repetir automaticamente. O trigger proíbe `launching -> reserved` e atualização posterior de hash/local do snapshot; grants de coluna sozinhos não impõem essa máquina de estados. Se a resposta IPC se perder após COMMIT, consultar status protegido pelo mesmo challenge; não consumir novamente.

Exemplo ilustrativo da transição, executado **somente** pelo broker depois das comparações e da criação do snapshot (não implementado nesta fase):

```sql
BEGIN;
UPDATE public.work_approval_launch_claims
   SET state = 'launching', launching_at = clock_timestamp(),
       snapshot_sha256 = %s, snapshot_location_id = %s
 WHERE id = %s::uuid AND state = 'reserved'
   AND snapshot_sha256 IS NULL AND snapshot_location_id IS NULL
 RETURNING id;
-- Exigir uma linha. Confirmar novamente hash/ACL do snapshot antes do spawn.
COMMIT;
```

## Ensaios futuros com portões distintos (nenhum executado)

### A. PostgreSQL 18 descartável: sintaxe, catálogo e privilégios

Neste portão só se avaliam DDL, constraints, catálogo, comportamento transacional e grants em cluster/bancos descartáveis. Não há serviço Windows, WebAuthn, IPC ou Codex real; aprovação aqui não libera o portão funcional nem work.

- Registrar `SELECT version()`/`current_user`/`session_user`, versão do pacote PostgresSaver e catálogo de schemas, owners, grants, memberships, default privileges, `rolbypassrls`, `relrowsecurity`, `search_path` e `CREATE`, sem senhas. Preparar dois bancos descartáveis: um vazio e outro com linhas de ensaio existentes. Confirmar que `ADD ... NOT NULL` direto falha no segundo e que estratégia expand/backfill/validate preserva dados; bloquear se bytes originais faltarem.
- Aplicar `000005`/delta e `setup()` offline no banco vazio; verificar `pg_constraint`, FKs, tipos reais e tabelas/migrations do PostgresSaver. Com DSN runtime restrito, testar somente DML de checkpoint e leitura de versão, sem `setup()`; versão errada deve falhar sem ALTER/CREATE.
- Com **login real** de cada role, além de `SET ROLE` por DBA para comparação, provar DML permitido e registrar SQLSTATE das negativas: agente sem ledger, verificador sem UPDATE de claim, broker sem INSERT de reserva/consumo de challenge, todos sem DDL/owner/`CREATE`/`SET ROLE` privilegiado. Para a evidência, `ws_approval_verifier` deve conseguir `SELECT` das sete colunas concedidas pelo `approval_id` e recomputar o hash dos bytes retornados; `SELECT captured_at`/`retain_until` e `SELECT` da evidência por checkpoint, broker, enroller e `PUBLIC` devem falhar. Conferir grants por coluna e herdados, membership transitiva, default privileges, `search_path`, funções `SECURITY DEFINER` e que `NOBYPASSRLS` não ativa RLS.
- Verificar a negativa de `PUBLIC` com um login de ensaio sem outros grants ou memberships; `PUBLIC` não é uma role de login. Não conceder SELECT de tabela inteira à role do verificador para fazer o teste passar.
- Com duas conexões, provar consumo único, UPDATE com `clock_timestamp()` no limite de expiração e ausência de aprovação/reserva após prazo. Induzir espera entre statements para distinguir `statement_timeout` de `transaction_timeout`/`idle_in_transaction_session_timeout`; rollback deve liberar locks. Exercitar negativos de máquina de estados, hash/location inválidos e imutabilidade de snapshot com login do broker. Restaurar backup em outra instância descartável e confirmar ledger preservado e `launching/unknown` sem replay.

### B. Ensaio funcional isolado: serviço, WebAuthn e Windows

Exige desenho e implantação isolados revisados antes de executar; sucesso do portão A não comprova este fluxo. Usar apenas repo/snapshot sintéticos e executor de ensaio sem Codex real.

- Com serviço e cliente protegidos, validar assertion real e vetor fixo do framing v1, recomputando `assertion_sha256` a partir dos cinco campos **lidos do ledger** antes do COMMIT. Trocar byte/presença em `rawId`, `userHandle`, `clientDataJSON`, `authenticatorData` e assinatura; negar handle/ID divergente, origin/RP/UV inválidos e leitura negada. Verificar retenção, ACL e auditoria de acesso aos bytes.
- Induzir verificação/assinatura lenta, exceção, falha de DB, resposta perdida após COMMIT, replay, troca de repo/HEAD/spec/plano/inventário e concorrência; deadline e `finally` devem encerrar sem lock persistente ou segundo claim. Testar o pipe com os SIDs reais: pré-criação, servidor falso, impersonação, downgrade, binding trocado, rede/remoto e instância adicional precisam falhar antes de expor assertion ou permitir launch.
- Trocar arquivo ou ACL entre observação e spawn; snapshot protegido deve conservar digest e `.git`. Simular crash antes/depois de `launching` e restaurar backup sem reabrir challenge nem relançar automaticamente; rollback operacional desabilita gate e preserva ledger.

### C. Work real

Permanece **NO-GO**. Requer revisão do portão funcional, separação efetiva de SIDs/DSNs, sandbox protegida, decisão posterior explícita e contrato próprio para review. Nenhum resultado do PG18 descartável autoriza remover `CODEX_STAGE_DISABLED` ou iniciar Codex real.

**Evidência desta entrega:** conferência estática contra a migration `000005` e código LangGraph local. Nenhum SQL, papel, migration ou teste PostgreSQL deste documento foi executado.

Referências de semântica PG18: [ALTER TABLE OWNER](https://www.postgresql.org/docs/18/sql-altertable.html), [Role Membership](https://www.postgresql.org/docs/18/role-membership.html), [GRANT por coluna](https://www.postgresql.org/docs/18/sql-grant.html), [Date/Time Functions](https://www.postgresql.org/docs/18/functions-datetime.html) e [Client Connection Defaults](https://www.postgresql.org/docs/18/runtime-config-client.html). `clock_timestamp()` avança até dentro de uma instrução; por isso o exemplo usa uma CTE para compartilhar o mesmo valor no predicado e em `consumed_at`. `transaction_timeout` limita a transação inteira, inclusive tempo entre statements; `statement_timeout` limita statements individuais.
