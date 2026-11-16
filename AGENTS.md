# Regras locais para demandas Jira

- Antes de analisar um Jira, prepare `C:\htdocs\Demandas\<CHAVE>` com `scripts/windows/demand.ps1`. O script usa `baixar-jira` para salvar XML, anexos e referências. Consulte o XML e as evidências nessa pasta.
- Crie o worktree de código dentro da pasta do Jira, em subpasta com nome do repositório ou papel (`webagil-back`, por exemplo). Informe repositório e branch base explicitamente. Não altere o checkout principal da pessoa.
- A branch da demanda deve ser criada a partir da base apropriada e publicada imediatamente com upstream na sua correspondente remota, `origin/<CHAVE>`. Confirme `git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'` no worktree. Upstream em `master`, `dev` ou outra branch não atende a regra.
- Não misture `qualid` ou QAS na branch da demanda. Use essas branches somente como referência, salvo instrução explícita em contrário.
- Acesso Oracle pelo script `scripts/windows/oracle-read.ps1` é somente leitura e limitado. Nunca registre segredos ou cópias de `.env` no projeto, nas notas ou na pasta da demanda.
- A pasta da demanda e o worktree não comprovam publicação de código, teste funcional ou conclusão do suporte. Registre cada evidência separadamente.

Comandos e fontes de configuração: [docs/access-scripts.md](docs/access-scripts.md).
