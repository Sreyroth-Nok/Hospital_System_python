"""
setup_database.py - One command to prepare MySQL for the first run.

It creates the database if it does not exist, builds every table, index
and view, and creates the default admin account.

Run:  python setup_database.py
"""

import config
from services import auth_service
from utils import database as db


def main():
    import sys
    if "--sqlite" in sys.argv:
        db.set_backend("sqlite")
    elif "--mysql" in sys.argv:
        db.set_backend("mysql")

    print(f"Backend  : {config.BACKEND}")
    if config.BACKEND == "mysql":
        print(f"Server   : {config.MYSQL['user']}@{config.MYSQL['host']}:{config.MYSQL['port']}")
        print(f"Database : {config.MYSQL['database']}")
    try:
        db.init_db()
        auth_service.ensure_default_admin()
    except db.DatabaseError as e:
        print(f"\nFailed: {e}")
        print("\nCheck that the MySQL server is running and that the user and "
              "password in config.py are correct.")
        print("Tip: To run locally with SQLite without MySQL, use:")
        print("     python setup_database.py --sqlite")
        return 1
    tables = db.query("SELECT COUNT(*) AS c FROM patients")
    print(f"\nReady. Driver: {db.driver_name()}")
    print(f"Patients currently stored: {tables[0]['c']}")
    print("Default login: admin / admin123")
    print("\nNext: python seed_data.py   then   python main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
