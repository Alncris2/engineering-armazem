"""Bounded, read-only Oracle access using the existing MCP env-file mapping."""

import argparse
import json
import re
import sys
from pathlib import Path


def env_values(path):
    values = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def validate(sql):
    clean = re.sub(r"/\*.*?\*/|--[^\n]*", " ", sql, flags=re.DOTALL)
    clean = re.sub(r"'(?:[^']|'')*'", "''", clean).strip()
    if not re.match(r"^(SELECT|WITH)\b", clean, re.IGNORECASE):
        raise ValueError("Somente SELECT/WITH é permitido")
    if ";" in clean or re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COMMIT|ROLLBACK|EXECUTE|EXEC|BEGIN|DECLARE|CALL|LOCK|RENAME|FLASHBACK|PURGE)\b|\bFOR\s+UPDATE\b", clean, re.IGNORECASE):
        raise ValueError("SQL contém múltiplas instruções ou comando não permitido")
    return sql.strip().rstrip(";")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--connect-by", choices=("sid", "service"), default="sid")
    parser.add_argument("--client-lib-dir")
    parser.add_argument("--sql-file")
    parser.add_argument("--params-file")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--max-rows", type=int, default=100)
    args = parser.parse_args()
    if args.probe == bool(args.sql_file) or not 1 <= args.max_rows <= 200:
        parser.error("Use --probe ou --sql-file e limite de 1 a 200")
    if args.probe and args.params_file:
        parser.error("O preflight não aceita parâmetros")
    import oracledb
    if args.client_lib_dir:
        oracledb.init_oracle_client(lib_dir=args.client_lib_dir)
    values = env_values(args.env_file)
    required = ("DB_HOST", "DB_USERNAME", "DB_PASSWORD")
    if any(not values.get(key) for key in required):
        raise ValueError("Arquivo Oracle sem campos de conexão necessários")
    if values.get("DB_TNS"):
        dsn = values["DB_TNS"]
    else:
        name = values.get("DB_DATABASE_SID") or values.get("DB_DATABASE")
        if not name:
            raise ValueError("Arquivo Oracle sem identificador de banco")
        kwargs = {"service_name" if args.connect_by == "service" else "sid": name}
        dsn = oracledb.makedsn(values["DB_HOST"], int(values.get("DB_PORT") or 1521), **kwargs)
    sql = ("SELECT SYS_CONTEXT('USERENV','DB_NAME') AS DB_NAME, "
           "SYS_CONTEXT('USERENV','CURRENT_SCHEMA') AS CURRENT_SCHEMA FROM DUAL"
           if args.probe else Path(args.sql_file).read_text(encoding="utf-8-sig"))
    sql = validate(sql)
    params = json.loads(Path(args.params_file).read_text(encoding="utf-8")) if args.params_file else {}
    if not isinstance(params, dict):
        raise ValueError("Parâmetros devem ser um objeto JSON")
    connection = oracledb.connect(user=values["DB_USERNAME"], password=values["DB_PASSWORD"], dsn=dsn)
    try:
        connection.call_timeout = 30000
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(sql, params)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(args.max_rows + 1)
            result = {"columns": columns, "rows": [list(row) for row in rows[:args.max_rows]],
                      "row_count": min(len(rows), args.max_rows), "truncated": len(rows) > args.max_rows}
            print(json.dumps(result, ensure_ascii=False, default=str))
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error": {"code": "ORACLE_READ_FAILED", "class": type(exc).__name__,
                                    "message": "Consulta Oracle falhou; detalhes de conexão não foram exibidos."}}))
        sys.exit(1)
