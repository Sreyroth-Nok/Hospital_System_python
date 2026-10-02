"""
main.py - Start the Hospital Appointment & Patient Management System.
Owner: Person 1

Run:  python main.py
"""

import sys
import tkinter.messagebox as messagebox

from gui.app import MainWindow
from gui.login_window import show_login
from services import auth_service
from utils import database as db


def main():
    if "--sqlite" in sys.argv:
        db.set_backend("sqlite")
    elif "--mysql" in sys.argv:
        db.set_backend("mysql")

    try:
        db.init_db()
        auth_service.ensure_default_admin()
    except db.DatabaseError as e:
        print(f"Cannot start: {e}")
        try:
            messagebox.showerror("Cannot start", str(e))
        except Exception:
            pass
        sys.exit(1)

    user = show_login()
    if user is None:
        sys.exit(0)

    window = MainWindow(user)
    window.mainloop()


if __name__ == "__main__":
    main()
