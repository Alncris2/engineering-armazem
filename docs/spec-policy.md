# Política de aprovação de spec

Template compartilhado: `config/templates/development-spec.md`. O estado inicial é `draft` e a seção `## Open Questions` contém um placeholder aberto. Antes de aprovar, resolva cada dúvida, registre a decisão no corpo da spec e deixe a seção com somente `Nenhuma.`. A existência de qualquer outra linha nessa seção, ou a ausência da seção, bloqueia a aprovação.

No LangGraph, `services/orchestrator/development/spec_gate.py` é chamado pelo `gate_plan`. O teste cobre o caso de confiança 99 com uma pergunta aberta e confirma que a run fica em hold sem `plan_record`.

Para o OpenSquad legado, `adapters/opensquad/spec-gate.mjs` e `scripts/windows/apply-opensquad-spec-gate.ps1` estão preparados para acrescentar o gate ao `approve-plan`, orientar Abel a gerar `spec.md` na run e copiar o template. **Essa aplicação em `C:\htdocs\squad-ia` está pendente:** a revisão automática rejeitou a escrita porque uma instrução anterior proibia modificar esse diretório e a mensagem posterior não foi considerada revogação inequívoca. Até a aplicação ser autorizada, o OpenSquad ainda pode aprovar um plano com Open Questions; não trate o gate como ativo lá.
