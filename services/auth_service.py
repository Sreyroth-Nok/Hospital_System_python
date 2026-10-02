"""
auth_service.py - Login, user accounts, roles and the audit log.
Owner: Person 1
"""

import hashlib
from utils import database as db
from utils.validator import now_stamp

ROLES = ("admin", "receptionist", "doctor")


def hash_password(plain):
    """Passwords are never stored in readable form."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def ensure_default_admin():
    """Create the first admin account so the system can be opened at all."""
    if db.query_one("SELECT username FROM users WHERE role = 'admin'") is None:
        db.execute(
            "INSERT INTO users (username, password_hash, role, linked_doctor_id,"
            " is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("admin", hash_password("admin123"), "admin", None, 1, now_stamp()),
        )


def login(username, password):
    """Return the user row for a correct login, otherwise None."""
    row = db.query_one(
        "SELECT * FROM users WHERE username = ? AND password_hash = ? AND is_active = 1",
        (username, hash_password(password)),
    )
    return row


def create_user(username, password, role, linked_doctor_id=None):
    if role not in ROLES:
        raise ValueError(f"Role must be one of: {', '.join(ROLES)}")
    if role == "doctor" and not linked_doctor_id:
        raise ValueError("A doctor account must be linked to a doctor record.")
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, role, linked_doctor_id,"
            " is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (username, hash_password(password), role, linked_doctor_id, now_stamp()),
        )
    except db.IntegrityError:
        raise ValueError(f"The username '{username}' is already taken.")


def deactivate_user(username):
    if username == "admin":
        raise ValueError("The main admin account cannot be deactivated.")
    changed = db.execute("UPDATE users SET is_active = 0 WHERE username = ?", (username,))
    if not changed:
        raise ValueError(f"No user called '{username}'.")


def reset_password(username, new_password):
    changed = db.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (hash_password(new_password), username),
    )
    if not changed:
        raise ValueError(f"No user called '{username}'.")


def list_users():
    return db.query("SELECT username, role, linked_doctor_id, is_active FROM users ORDER BY role, username")


def log_action(username, action):
    """Write one line to the audit log. Never stops the caller if it fails."""
    try:
        db.execute(
            "INSERT INTO audit_log (username, action, timestamp) VALUES (?, ?, ?)",
            (username, action, now_stamp()),
        )
    except Exception:
        pass


def read_audit_log(limit=50):
    return db.query(
        "SELECT username, action, timestamp FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,),
    )
