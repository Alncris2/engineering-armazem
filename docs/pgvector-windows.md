# Instalação do pgvector no PostgreSQL 18 deste Windows

Estado em 2026-11-13: **arquivos do pgvector 0.8.7 instalados pelo usuário e verificados**. `pg_config --version` e `psql --version` retornaram PostgreSQL 18.7; serviço `postgresql-x64-18` está `Running`. `lib\vector.dll` (266752 bytes), `share\extension\vector.control` e `share\extension\vector--0.8.7.sql` existem; o control declara `default_version = '0.8.7'`. A consulta SQL com `psql -X -w -U postgres -d postgres` falhou com `fe_sendauth: no password supplied`. Logo, a disponibilidade registrada pelo servidor e a habilitação por banco ainda não foram confirmadas. Não se solicitou nem exibiu senha.

O procedimento abaixo fica como registro para reprodução futura; **não precisa ser executado novamente agora**. `nmake.exe` está instalado no Visual Studio 2019 Build Tools, mas não no PATH do PowerShell comum. `vcvars64.bat` carrega o ambiente C++ e `where nmake` então encontra o executável.

O [procedimento oficial do pgvector para Windows](https://github.com/pgvector/pgvector/blob/master/README.md#installation) usa o código da tag `v0.8.7`, `PGROOT` e `nmake`. Os comandos abaixo marcados `cmd` são para **cmd.exe**, não para PowerShell. Em PowerShell 7, `call` não existe. Para abrir um `cmd.exe` filho com o ambiente C++ carregado, executar no PowerShell com permissão administrativa:

```powershell
$vcvars = 'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat'
& $env:ComSpec /d /k ('call "' + $vcvars + '"')
```

O comando de verificação equivalente com `/c` e `where nmake` foi testado nesta sessão e encontrou o executável. Dentro do novo prompt `cmd.exe`, executar:

```cmd
where nmake
```

Se abrir um `cmd.exe` comum em vez do prompt x64, carregar primeiro o ambiente C++:

```cmd
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
where nmake
```

Em seguida, no mesmo terminal:

```cmd
set "PGROOT=C:\Program Files\PostgreSQL\18"
cd /d C:\htdocs\ai-engineering-workspace
if not exist build mkdir build
git clone --branch v0.8.7 --depth 1 https://github.com/pgvector/pgvector.git build\pgvector
cd /d C:\htdocs\ai-engineering-workspace\build\pgvector
nmake /F Makefile.win
nmake /F Makefile.win install
```

`build/` é ignorado pelo Git. Antes de executar, confirmar que `build\pgvector` ainda não existe. Após a instalação, verificar que `C:\Program Files\PostgreSQL\18\lib\vector.dll` e `C:\Program Files\PostgreSQL\18\share\extension\vector.control` existem. Para habilitar em um banco escolhido, executar `CREATE EXTENSION vector;` com uma conta autorizada e verificar `SELECT extversion FROM pg_extension WHERE extname = 'vector';`. A extensão é habilitada por banco; estes comandos SQL não foram executados nesta etapa. Não colocar senha na linha de comando nem neste documento.
