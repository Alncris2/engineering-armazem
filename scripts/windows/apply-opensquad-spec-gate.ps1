$ErrorActionPreference = 'Stop'

$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$target = [IO.Path]::GetFullPath('C:\htdocs\squad-ia')
$routerPath = Join-Path $target 'tools\opensquad\route.mjs'
$analysisPath = Join-Path $target 'squads\webagil-dev\pipeline\steps\step-02-analyze-task.md'
$approvalPath = Join-Path $target 'squads\webagil-dev\pipeline\steps\step-03-approve-plan.md'
$gatePath = Join-Path $target 'tools\opensquad\spec-gate.mjs'
$templatePath = Join-Path $target 'squads\webagil-dev\pipeline\templates\development-spec.md'

foreach ($file in @($routerPath, $analysisPath, $approvalPath)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or
        -not $file.StartsWith($target + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Alvo inválido: $file"
    }
}

$router = Get-Content -LiteralPath $routerPath -Raw -Encoding utf8
$analysis = Get-Content -LiteralPath $analysisPath -Raw -Encoding utf8
$approval = Get-Content -LiteralPath $approvalPath -Raw -Encoding utf8

$import = 'import { checkSpecOpenQuestions } from "./spec-gate.mjs";'
$guard = @'
if (from === "approve-plan" && nonemptyLines[0] === "plano-aprovado") {
  const specPath = path.join(runRoot, "spec.md");
  const stat = fs.lstatSync(specPath, { throwIfNoEntry: false });
  if (!stat?.isFile() || stat.isSymbolicLink()) throw new Error("Spec da run ausente ou inválida");
  const verdict = checkSpecOpenQuestions(fs.readFileSync(specPath, "utf8"));
  if (!verdict.ok) throw new Error(verdict.reason);
}
'@
$analysisNote = 'Para CAMINHO: PLANEJADO, escreva também `squads/webagil-dev/output/{run_id}/spec.md` usando `pipeline/templates/development-spec.md`. Resolva dúvidas verificáveis no card, código e ferramentas. Mantenha toda dúvida ainda aberta em `## Open Questions`; a spec não pode ser aprovada enquanto houver qualquer item nessa seção. Após a decisão, incorpore-a no corpo da spec e deixe a seção com apenas `Nenhuma.`.'
$approvalNote = 'Antes de registrar `plano-aprovado`, leia `spec.md` da run. Se `## Open Questions` contiver qualquer dúvida, peça a decisão necessária e registre `ajustes-solicitados`; não aprove nem avance. Quando resolvida, incorpore a decisão à spec e deixe nessa seção somente `Nenhuma.`. O roteador aplica esse bloqueio mesmo que `plan-decision.md` diga `plano-aprovado`.'

if (-not $router.Contains($import)) {
    $anchor = 'import path from "node:path";'
    if (-not $router.Contains($anchor)) { throw 'Âncora de importação não encontrada' }
    $router = $router.Replace($anchor, "$anchor`n$import")
}
if (-not $router.Contains('const verdict = checkSpecOpenQuestions')) {
    $anchor = 'if (from === "review-code" && !/^VEREDICTO:'
    $at = $router.IndexOf($anchor, [StringComparison]::Ordinal)
    if ($at -lt 0) { throw 'Âncora do gate não encontrada' }
    $router = $router.Insert($at, "$guard`n")
}
if (-not $analysis.Contains($analysisNote)) {
    $anchor = '## Veto Conditions'
    if (-not $analysis.Contains($anchor)) { throw 'Âncora da análise não encontrada' }
    $analysis = $analysis.Replace($anchor, "$analysisNote`n`n$anchor")
}
if (-not $approval.Contains($approvalNote)) {
    $anchor = 'Se o usuário já autorizou o plano'
    if (-not $approval.Contains($anchor)) { throw 'Âncora da aprovação não encontrada' }
    $approval = $approval.Replace($anchor, "$approvalNote`n`n$anchor")
}

$utf8 = New-Object System.Text.UTF8Encoding $false
[IO.File]::WriteAllText($routerPath, $router, $utf8)
[IO.File]::WriteAllText($analysisPath, $analysis, $utf8)
[IO.File]::WriteAllText($approvalPath, $approval, $utf8)
Copy-Item -LiteralPath (Join-Path $workspace 'adapters\opensquad\spec-gate.mjs') -Destination $gatePath
New-Item -ItemType Directory -Path (Split-Path -Parent $templatePath) -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $workspace 'config\templates\development-spec.md') -Destination $templatePath
Write-Output 'OPENSQUAD_SPEC_GATE:APPLIED'
