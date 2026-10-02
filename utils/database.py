"""
database.py - The only module that talks to the database server.
Owner: Person 1

The system runs on MySQL. Every other module calls query(), query_one()
and execute() with ? placeholders and never imports a driver itself, so
the rest of the program does not change if the storage changes.

A 'sqlite' backend is kept in config.py so the team can work on a laptop
with no MySQL server installed. The SQL is the same either way.
"""

import os
import re

import config

BACKEND = getattr(config, "BACKEND", "mysql")


def set_backend(name):
    """Switch backend dynamically between 'mysql' and 'sqlite'."""
    global _driver, _driver_name, BACKEND
    config.BACKEND = name
    BACKEND = name
    _driver = None
    _driver_name = None


def get_backend():
    return getattr(config, "BACKEND", "mysql")


# --------------------------------------------------------------- errors
class DatabaseError(Exception):
    """Raised when the database cannot be reached or a statement fails."""


class IntegrityError(DatabaseError):
    """Raised when a UNIQUE, CHECK or FOREIGN KEY rule refuses a write.

    Both drivers raise their own class; services catch this one instead.
    """


# --------------------------------------------------------------- driver
_driver = None
_driver_name = None


def _load_driver():
    """Import the driver once, and say clearly what to install if it is missing."""
    global _driver, _driver_name
    if _driver is not None:
        return _driver

    if get_backend() == "sqlite":
        import sqlite3
        _driver, _driver_name = sqlite3, "sqlite3"
        return _driver

    try:
        import mysql.connector as driver
        _driver_name = "mysql.connector"
    except ImportError:
        try:
            import pymysql as driver
            _driver_name = "pymysql"
        except ImportError:
            raise DatabaseError(
                "No MySQL driver found. Install one with:\n"
                "    pip install mysql-connector-python\n"
                "or set BACKEND = 'sqlite' in config.py to work offline."
            )
    _driver = driver
    return _driver


def driver_name():
    _load_driver()
    return _driver_name


# ----------------------------------------------------------- connection
def get_connection():
    """Open a connection whose rows come back as dictionaries."""
    driver = _load_driver()
    try:
        if get_backend() == "sqlite":
            os.makedirs(config.DATA_DIR, exist_ok=True)
            conn = driver.connect(config.SQLITE_PATH)
            conn.row_factory = driver.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        if _driver_name == "mysql.connector":
            return driver.connect(**config.MYSQL)
        settings = dict(config.MYSQL)
        settings["cursorclass"] = driver.cursors.DictCursor
        return driver.connect(**settings)
    except Exception as e:
        raise DatabaseError(f"Cannot connect to the database: {e}")


def _server_connection():
    """Connect to MySQL without naming a database, so it can be created."""
    driver = _load_driver()
    settings = {k: v for k, v in config.MYSQL.items() if k != "database"}
    if _driver_name == "pymysql":
        settings["cursorclass"] = driver.cursors.DictCursor
    try:
        return driver.connect(**settings)
    except Exception as e:
        raise _wrap_error(e)


def _cursor(conn):
    if get_backend() == "sqlite":
        return conn.cursor()
    if _driver_name == "mysql.connector":
        return conn.cursor(dictionary=True)
    return conn.cursor()


def _sql(statement):
    """SQL is written once with ? placeholders; MySQL wants %s."""
    if get_backend() == "sqlite":
        return statement
    return statement.replace("?", "%s")


def _clean(value):
    """Decimal and date objects become the plain types the app works with."""
    if value is None or isinstance(value, (str, int, float, bytes)):
        return value
    try:
        import decimal
        if isinstance(value, decimal.Decimal):
            return float(value)
    except ImportError:
        pass
    return str(value)


def _row(raw):
    """One row as a plain dict, whichever driver produced it."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return {k: _clean(v) for k, v in raw.items()}
    return {k: _clean(raw[k]) for k in raw.keys()}


def _wrap_error(e):
    driver = _load_driver()
    integrity = getattr(driver, "IntegrityError", None)
    if integrity and isinstance(e, integrity):
        return IntegrityError(str(e))
    return DatabaseError(str(e))


# ------------------------------------------------------------ statements
def query(sql, params=()):
    """Run a SELECT and return every row as a dict."""
    conn = get_connection()
    try:
        cur = _cursor(conn)
        cur.execute(_sql(sql), tuple(params))
        return [_row(r) for r in cur.fetchall()]
    except Exception as e:
        raise _wrap_error(e)
    finally:
        conn.close()


def query_one(sql, params=()):
    """Run a SELECT and return the first row, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    """Run an INSERT, UPDATE or DELETE, commit it, and return the row count."""
    conn = get_connection()
    try:
        cur = _cursor(conn)
        cur.execute(_sql(sql), tuple(params))
        conn.commit()
        return cur.rowcount
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        raise _wrap_error(e)
    finally:
        conn.close()


def execute_script(statements):
    """Run several statements in one connection, used for the schema."""
    conn = get_connection()
    try:
        cur = _cursor(conn)
        for statement in statements:
            if statement.strip():
                cur.execute(statement)
        conn.commit()
    except Exception as e:
        raise _wrap_error(e)
    finally:
        conn.close()


# ---------------------------------------------------------------- schema
def _split_statements(text):
    """Split a .sql file on semicolons, ignoring comment lines."""
    lines = [l for l in text.splitlines() if not l.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def create_database_if_missing():
    """CREATE DATABASE hospital_db, so a fresh MySQL server is enough."""
    if get_backend() == "sqlite":
        return
    conn = _server_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS {config.MYSQL['database']} "
            f"CHARACTER SET utf8mb4"
        )
        conn.commit()
    except Exception as e:
        raise _wrap_error(e)
    finally:
        conn.close()


def init_db():
    """Create every table, index and view. Safe to run more than once."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(config.DATA_DIR, "receipts"), exist_ok=True)
    create_database_if_missing()

    path = config.SCHEMA_SQLITE if get_backend() == "sqlite" else config.SCHEMA_MYSQL
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise DatabaseError(f"Schema file not found: {path}")
    execute_script(_split_statements(text))


def next_id(table, prefix, width=3):
    """Build the next ID, for example P001 or INV004.

    Counts from the highest existing number rather than from the row count,
    so deleting a row can never produce a duplicate ID.
    """
    rows = query(f"SELECT id FROM {table} WHERE id LIKE ?", (f"{prefix}%",))
    highest = 0
    for row in rows:
        tail = str(row["id"])[len(prefix):]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"{prefix}{highest + 1:0{width}d}"


def weekday_expression(column="`date`"):
    """The one query that differs between the two engines."""
    if get_backend() == "sqlite":
        return (f"CASE strftime('%w', {column}) "
                "WHEN '0' THEN 'Sunday'   WHEN '1' THEN 'Monday' "
                "WHEN '2' THEN 'Tuesday'  WHEN '3' THEN 'Wednesday' "
                "WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' "
                "ELSE 'Saturday' END")
    return f"DAYNAME(STR_TO_DATE({column}, '%Y-%m-%d'))"


def connection_label():
    """Shown in the status bar of the GUI."""
    if get_backend() == "sqlite":
        return f"SQLite · {os.path.basename(config.SQLITE_PATH)}"
    return f"MySQL · {config.MYSQL['database']} @ {config.MYSQL['host']}"
