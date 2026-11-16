// Deterministic gate used by the legacy OpenSquad development router.
export function checkSpecOpenQuestions(markdown) {
  if (typeof markdown !== "string") return { ok: false, reason: "Spec ausente" };
  const text = markdown.replace(/<!--[\s\S]*?-->/g, "");
  const match = /^##\s+Open Questions\s*$/im.exec(text);
  if (!match) return { ok: false, reason: "Seção Open Questions ausente" };
  const rest = text.slice(match.index + match[0].length);
  const boundary = /^#{1,2}\s+/m.exec(rest);
  const section = (boundary ? rest.slice(0, boundary.index) : rest).trim();
  if (section === "Nenhuma." || section === "None.") {
    return { ok: true, reason: "Nenhuma open question" };
  }
  return { ok: false, reason: "Open Questions deve conter somente 'Nenhuma.' antes da aprovação" };
}
