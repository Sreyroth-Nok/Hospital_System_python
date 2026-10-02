"""
login_window.py - The first screen. Three tries, then the program closes.
Owner: Person 1
"""

import tkinter as tk
from tkinter import ttk

from gui import widgets
from services import auth_service
from utils import database as db

MAX_ATTEMPTS = 3


class LoginWindow(tk.Tk):
    """Asks for a username and password and keeps the row of whoever logs in."""

    def __init__(self):
        super().__init__()
        self.user = None
        self.attempts = 0

        self.title("Hospital System - Sign in")
        self.resizable(False, False)
        widgets.apply_theme(self)

        card = ttk.Frame(self, style="Card.TFrame", padding=30)
        card.pack(padx=30, pady=30)

        ttk.Label(card, text="City General Hospital", style="Heading.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="Appointment & Patient Management",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=2,
                                             sticky="w", pady=(0, 18))

        self.username = tk.StringVar()
        self.password = tk.StringVar()

        ttk.Label(card, text="Username", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", pady=6, padx=(0, 12))
        user_entry = ttk.Entry(card, textvariable=self.username, width=26)
        user_entry.grid(row=2, column=1, pady=6)

        ttk.Label(card, text="Password", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", pady=6, padx=(0, 12))
        password_entry = ttk.Entry(card, textvariable=self.password, show="*", width=26)
        password_entry.grid(row=3, column=1, pady=6)

        self.message = ttk.Label(card, text="", foreground=widgets.DANGER,
                                 style="Card.TLabel", wraplength=260)
        self.message.grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

        ttk.Button(card, text="Sign in", command=self.attempt_login,
                   style="Primary.TButton").grid(row=5, column=0, columnspan=2,
                                                 sticky="ew", pady=(16, 0))

        ttk.Label(card, text=db.connection_label(), style="Muted.TLabel").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(14, 0))

        self.bind("<Return>", lambda event: self.attempt_login())
        user_entry.focus_set()
        self._centre()

    def _centre(self):
        self.update_idletasks()
        width, height = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def attempt_login(self):
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            self.message.configure(text="Type both a username and a password.")
            return
        try:
            row = auth_service.login(username, password)
        except db.DatabaseError as e:
            self.message.configure(text=str(e))
            return

        if row:
            self.user = row
            auth_service.log_action(username, "Logged in")
            self.destroy()
            return

        self.attempts += 1
        left = MAX_ATTEMPTS - self.attempts
        self.password.set("")
        if left <= 0:
            widgets.error("Too many failed attempts. The program will close.",
                          "Sign in failed")
            self.user = None
            self.destroy()
            return
        self.message.configure(
            text=f"Wrong username or password. {left} attempt(s) left.")


def show_login():
    """Run the login window and return the signed-in user row, or None."""
    window = LoginWindow()
    window.mainloop()
    return window.user
