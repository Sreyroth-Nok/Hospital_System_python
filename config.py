"""
config.py - Where the system stores its data.
Owner: Person 1

Edit MYSQL below to match your own MySQL server, then run:
    python setup_database.py
"""

import os

# "mysql" for the real system. "sqlite" is a fallback for working on a laptop
# with no MySQL server installed; the application code is identical either way.
BACKEND = os.environ.get("HOSPITAL_BACKEND", "mysql")

MYSQL = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("MYSQL_PORT", 3306)),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DB", "hospital_db"),
    "charset": "utf8mb4",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SQLITE_PATH = os.path.join(DATA_DIR, "hospital.db")

SCHEMA_MYSQL = os.path.join(DATA_DIR, "schema_mysql.sql")
SCHEMA_SQLITE = os.path.join(DATA_DIR, "schema_sqlite.sql")

APP_TITLE = "City General Hospital - Appointment & Patient Management"
