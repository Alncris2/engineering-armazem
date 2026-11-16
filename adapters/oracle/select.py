"""Execute one bounded SELECT in a read-only Oracle transaction."""

import argparse
import json
import os
import re
import sys


def validate_sql(sql):
    value = sql.strip()
    if not re.match(r"^(SELECT|WITH)\b", value, re.IGNORECASE) or ";" in value:
        raise ValueError("Only one SELECT or WITH statement is allowed")
    if re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|EXECUTE)\b", value, re.IGNORECASE):
        raise ValueError("Write or DDL keyword is not allowed")
    return value


def select(sql, limit):
    import oracledb
    statement = validate_sql(sql)
    connection = oracledb.connect(user=os.environ["ORACLE_USER"], password=os.environ["ORACLE_PASSWORD"],
                                  dsn=os.environ["ORACLE_DSN"])
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(statement)
            names = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(limit)
            return {"columns": names, "rows": [list(row) for row in rows], "truncated": bool(cursor.fetchone())}
    finally:
        connection.rollback()
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", required=True)
    parser.add_argument("--max-rows", type=int, default=100)
    args = parser.parse_args()
    try:
        if args.max_rows < 1 or args.max_rows > 1000:
            raise ValueError("Invalid row limit")
        print(json.dumps({"data": select(args.sql, args.max_rows), "error": None}, default=str))
    except Exception:
        print(json.dumps({"data": None, "error": {"code": "ORACLE_READ_FAILED",
                                                 "message": "Oracle SELECT failed or is not configured"}}))
        sys.exit(1)
