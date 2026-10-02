"""
users_tab.py - Staff accounts and roles. Admins only.
Owner: Person 1
"""

from tkinter import ttk

from gui import widgets
from gui.widgets import DataTable, FormDialog, Toolbar
from services import auth_service, doctor_service
from utils import database as db

COLUMNS = [
    ("username", "Username", 160), ("role", "Role", 140),
    ("linked_doctor", "Linked doctor", 200), ("state", "Status", 100),
]


class UsersTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Card.TFrame", padding=14)
        self.app = app

        ttk.Label(self, text="User accounts", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="Passwords are stored as a SHA-256 hash, never as text. "
                             "A doctor account sees only its own appointments.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        Toolbar(self, [
            ("Create user", self.create, "primary"),
            ("Reset password", self.reset, None),
            ("Deactivate", self.deactivate, "danger"),
            ("Refresh", self.refresh, None),
        ]).pack(fill="x")

        self.table = DataTable(self, COLUMNS, height=12)
        self.table.pack(fill="both", expand=True, pady=(10, 0))
        self.refresh()

    def refresh(self):
        try:
            users = auth_service.list_users()
            doctors = {d.id: d.name for d in doctor_service.get_all(active_only=False)}
        except db.DatabaseError as e:
            widgets.error(str(e))
            return
        self.table.set_rows(users, formatter=lambda u: {
            "username": u["username"], "role": u["role"],
            "linked_doctor": doctors.get(u["linked_doctor_id"], "-"),
            "state": "active" if u["is_active"] else "inactive",
        })

    def _selected(self):
        username = self.table.selected_value("username")
        if username is None:
            widgets.error("Choose a user from the list first.", "Nothing selected")
        return username

    def create(self):
        doctors = doctor_service.get_all(active_only=False)
        values = FormDialog.open(self, "Create a user", [
            {"key": "username", "label": "Username", "kind": "text", "max_len": 30},
            {"key": "password", "label": "Password", "kind": "text", "secret": True},
            {"key": "role", "label": "Role", "kind": "choice",
             "options": list(auth_service.ROLES), "default": "receptionist"},
            {"key": "linked", "label": "Doctor (only for a doctor account)",
             "kind": "choice", "required": False,
             "options": [""] + [f"{d.id} - {d.name}" for d in doctors]},
        ], submit_label="Create",
            intro="A doctor account must be linked to a doctor record.")
        if not values:
            return
        linked = values["linked"].split(" - ")[0] if values["linked"] else None
        try:
            auth_service.create_user(values["username"], values["password"],
                                     values["role"], linked)
        except (ValueError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Created user {values['username']}")
        widgets.info(f"Account '{values['username']}' created.")
        self.refresh()

    def reset(self):
        username = self._selected()
        if username is None:
            return
        values = FormDialog.open(self, f"Reset password for {username}", [
            {"key": "password", "label": "New password", "kind": "text", "secret": True},
        ], submit_label="Reset")
        if not values:
            return
        try:
            auth_service.reset_password(username, values["password"])
        except (ValueError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Reset password for {username}")
        widgets.info("Password reset.")

    def deactivate(self):
        username = self._selected()
        if username is None:
            return
        if not widgets.ask(f"Deactivate '{username}'? They will not be able to sign in."):
            return
        try:
            auth_service.deactivate_user(username)
        except (ValueError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Deactivated user {username}")
        self.refresh()
