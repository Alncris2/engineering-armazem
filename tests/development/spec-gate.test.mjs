import assert from "node:assert/strict";
import { checkSpecOpenQuestions } from "../../adapters/opensquad/spec-gate.mjs";

assert.equal(checkSpecOpenQuestions("# Spec\n\n## Open Questions\n\nNenhuma.").ok, true);
assert.equal(checkSpecOpenQuestions("# Spec\n\n## Open Questions\n\n- Quem aprova?").ok, false);
assert.equal(checkSpecOpenQuestions("# Spec\n\n## Objetivo\n\nTexto").ok, false);
assert.equal(checkSpecOpenQuestions("## Open Questions\n\nNenhuma.\n\n- Ainda resta uma dúvida").ok, false);
console.log("SPEC_GATE_JS:PASS");
