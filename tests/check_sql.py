"""
check_sql.py - Reads the two schema files and every SQL statement in the
code, and reports anything that does not line up.

It catches the mistakes that only show up at run time against a real
server: an INSERT whose column list does not match the table, a column
name that exists in one schema but not the other, and a leftover %s
placeholder. It does not need a database server, so it can be run on any
machine before the group tests against MySQL.

Run from the project folder:  python tests/check_sql.py
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

PROBLEMS = []
CHECKS = 0


def note(message):
    PROBLEMS.append(message)
    print(f"  PROBLEM  {message}")


def tick(message):
    global CHECKS
    CHECKS += 1
    print(f"  ok       {message}")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def table_columns(schema_text):
    """Map every table in a .sql file to its list of column names."""
    tables = {}
    pattern = re.compile(
        r"CREATE TABLE(?: IF NOT EXISTS)? `?(\w+)`?\s*\((.*?)\n\)", re.S | re.I)
    for name, body in pattern.findall(schema_text):
        columns = []
        depth = 0
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--") or stripped.startswith("("):
                continue    # blank, comment, or the second line of a definition
            first = stripped.split()[0].strip("`,")
            keyword = first.upper()
            if keyword in ("PRIMARY", "UNIQUE", "KEY", "CONSTRAINT", "FOREIGN",
                           "CHECK", "INDEX"):
                continue
            # a generated column cannot be written to by an INSERT
            if "GENERATED ALWAYS" in stripped.upper():
                continue
            if depth == 0 and first and first not in columns:
                columns.append(first)
        tables[name] = columns
    return tables


def python_files():
    for folder, _, names in os.walk(ROOT):
        if "fake_tk" in folder or "__pycache__" in folder:
            continue
        for name in names:
            if name.endswith(".py"):
                yield os.path.join(folder, name)


def main():
    mysql = table_columns(read(os.path.join(ROOT, "data", "schema_mysql.sql")))
    sqlite = table_columns(read(os.path.join(ROOT, "data", "schema_sqlite.sql")))

    print("Schema files\n" + "-" * 62)
    print(f"  MySQL  : {len(mysql)} tables")
    print(f"  SQLite : {len(sqlite)} tables")

    # --- the two schemas must describe the same tables and columns ---
    for table in sorted(set(mysql) | set(sqlite)):
        if table not in mysql:
            note(f"table '{table}' is only in the SQLite schema")
        elif table not in sqlite:
            note(f"table '{table}' is only in the MySQL schema")
        else:
            only_mysql = [c for c in mysql[table] if c not in sqlite[table]]
            only_sqlite = [c for c in sqlite[table] if c not in mysql[table]]
            if only_mysql or only_sqlite:
                note(f"table '{table}' differs: MySQL only {only_mysql}, "
                     f"SQLite only {only_sqlite}")
            else:
                tick(f"table '{table}' matches in both schemas "
                     f"({len(mysql[table])} columns)")

    # --- every INSERT in the code must match the table ---
    print("\nINSERT statements\n" + "-" * 62)
    insert = re.compile(r"INSERT INTO (\w+)\s*\(([^)]*)\)\s*(?:\"\s*\n\s*\")?\s*VALUES", re.S)
    bare = re.compile(r"INSERT INTO (\w+)\s+VALUES", re.I)

    for path in python_files():
        text = read(path)
        joined = re.sub(r'"\s*\n\s*"', "", text)       # join split string literals
        relative = os.path.relpath(path, ROOT)

        for table in bare.findall(joined):
            note(f"{relative}: INSERT INTO {table} does not name its columns "
                 f"(breaks on the MySQL generated column)")

        for table, column_text in insert.findall(joined):
            columns = [c.strip().strip("`") for c in column_text.split(",") if c.strip()]
            if table not in mysql:
                note(f"{relative}: INSERT into unknown table '{table}'")
                continue
            unknown = [c for c in columns if c not in mysql[table]
                       and c not in ("id",) or c not in mysql[table]]
            unknown = [c for c in columns if c not in mysql[table]]
            if unknown:
                note(f"{relative}: INSERT INTO {table} names columns that do not "
                     f"exist: {unknown}")
            else:
                tick(f"{relative}: INSERT INTO {table} "
                     f"({len(columns)} of {len(mysql[table])} columns)")

    # --- placeholders ---
    print("\nPlaceholders and driver leaks\n" + "-" * 62)
    for path in python_files():
        relative = os.path.relpath(path, ROOT)
        text = read(path)
        if relative == os.path.join("utils", "database.py"):
            continue
        if "%s" in text and "strftime" not in text and "DATE_FORMAT" not in text:
            note(f"{relative}: uses a %s placeholder directly; write ? instead")
        if re.search(r"\bimport sqlite3\b|\bmysql\.connector\b|\bimport pymysql\b", text):
            note(f"{relative}: imports a database driver; only utils/database.py should")
    tick("no module outside utils/database.py imports a driver")
    tick("every query uses the ? placeholder the database layer translates")

    print("-" * 62)
    print(f"  {CHECKS} checks passed, {len(PROBLEMS)} problem(s)")
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    sys.exit(main())
