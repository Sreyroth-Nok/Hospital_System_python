"""
app.py - The main window: a dashboard plus one tab per area of work.
Owner: Person 1

Which tabs appear depends on the role of whoever signed in.
"""

import tkinter as tk
from tkinter import ttk

import config
from gui import widgets
from gui.appointments_tab import AppointmentsTab
from gui.billing_tab import BillingTab
from gui.doctors_tab import DoctorsTab
from gui.patients_tab import PatientsTab
from gui.reports_tab import ReportsTab
from gui.users_tab import UsersTab
from gui.widgets import DataTable
from services import appointment_service, auth_service, patient_service, report_service
from utils import database as db
from utils.validator import today

HISTORY_COLUMNS = [
    ("date", "Date", 100), ("time", "Time", 70), ("doctor_name", "Doctor", 170),
    ("specialization", "Specialization", 150), ("diagnosis", "Diagnosis", 220),
    ("status", "Status", 90), ("grand_total", "Total", 90),
    ("payment_status", "Payment", 90),
]


class MainWindow(tk.Tk):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.username = user["username"]
        self.role = user["role"]
        self.linked_doctor_id = user["linked_doctor_id"]

        self.title(f"{config.APP_TITLE}  -  {self.username} ({self.role})")
        self.geometry("1180x720")
        self.minsize(1000, 620)
        widgets.apply_theme(self)

        self._build_header()
        self._build_tabs()
        self._build_status_bar()
        self.refresh_dashboard()
        self.protocol("WM_DELETE_WINDOW", self.sign_out)

    # -------------------------------------------------------------- header
    def _build_header(self):
        header = ttk.Frame(self, padding=(16, 12, 16, 8))
        header.pack(fill="x")
        ttk.Label(header, text="City General Hospital", style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Sign out", command=self.sign_out).pack(side="right")

        self.stats = ttk.Frame(self, padding=(16, 0, 16, 10))
        self.stats.pack(fill="x")
        self.stat_labels = {}
        for key, caption in (("patients", "Patients"), ("doctors", "Active doctors"),
                             ("today", "Today's visits"), ("unpaid", "Unpaid invoices"),
                             ("income", "Collected")):
            card = ttk.Frame(self.stats, style="Card.TFrame", padding=12)
            card.pack(side="left", padx=(0, 10))
            value = ttk.Label(card, text="-", style="Stat.TLabel")
            value.pack(anchor="w")
            ttk.Label(card, text=caption, style="Muted.TLabel").pack(anchor="w")
            self.stat_labels[key] = value

    # ---------------------------------------------------------------- tabs
    def _build_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.tabs = {}

        if self.role == "doctor":
            self.tabs["appointments"] = DoctorTab(self.notebook, self)
            self.notebook.add(self.tabs["appointments"], text="My appointments")
            return

        self.tabs["patients"] = PatientsTab(self.notebook, self)
        self.tabs["appointments"] = AppointmentsTab(self.notebook, self)
        self.tabs["doctors"] = DoctorsTab(self.notebook, self)
        self.tabs["billing"] = BillingTab(self.notebook, self)
        self.tabs["reports"] = ReportsTab(self.notebook, self)
        self.notebook.add(self.tabs["patients"], text="Patients")
        self.notebook.add(self.tabs["appointments"], text="Appointments")
        self.notebook.add(self.tabs["doctors"], text="Doctors")
        self.notebook.add(self.tabs["billing"], text="Billing & pharmacy")
        self.notebook.add(self.tabs["reports"], text="Reports")

        if self.role == "admin":
            self.tabs["users"] = UsersTab(self.notebook, self)
            self.notebook.add(self.tabs["users"], text="Users")

    # ---------------------------------------------------------- status bar
    def _build_status_bar(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", side="bottom")
        self.status = ttk.Label(bar, text="", style="Status.TLabel", padding=(14, 6))
        self.status.pack(fill="x")
        self.set_status(f"Signed in as {self.username} · {db.connection_label()}")

    def set_status(self, message):
        self.status.configure(text=message)

    # ----------------------------------------------------------- dashboard
    def refresh_dashboard(self):
        try:
            summary = report_service.patient_summary()
            today_rows = appointment_service.by_date(today())
            unpaid = db.query_one("SELECT COUNT(*) AS c FROM invoices "
                                  "WHERE payment_status = 'Unpaid'")
        except db.DatabaseError as e:
            self.set_status(f"Database problem: {e}")
            return
        self.stat_labels["patients"].configure(text=str(summary["patients"]))
        self.stat_labels["doctors"].configure(text=str(summary["doctors"]))
        self.stat_labels["today"].configure(text=str(len(today_rows)))
        self.stat_labels["unpaid"].configure(text=str(unpaid["c"]))
        self.stat_labels["income"].configure(text=widgets.money(summary["income"]))

    # -------------------------------------------------------------- shared
    def show_patient_history(self, patient_id, patient_name):
        """Opened from the patients tab and from the doctor's screen."""
        try:
            rows = patient_service.visit_history(patient_id)
        except db.DatabaseError as e:
            widgets.error(str(e))
            return

        window = tk.Toplevel(self)
        window.title(f"Visit history - {patient_name} ({patient_id})")
        window.configure(background=widgets.SURFACE)
        frame = ttk.Frame(window, style="Card.TFrame", padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Visit history - {patient_name}",
                  style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text=f"{len(rows)} visit(s), newest first",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        table = DataTable(frame, HISTORY_COLUMNS, height=12)
        table.pack(fill="both", expand=True)
        table.set_rows(rows, formatter=lambda r: dict(
            r, diagnosis=r["diagnosis"] or "-",
            grand_total=widgets.money(r["grand_total"]) if r["grand_total"] else "-",
            payment_status=r["payment_status"] or "-"))
        ttk.Button(frame, text="Close", command=window.destroy).pack(anchor="e", pady=(10, 0))

    def sign_out(self):
        if not widgets.ask("Sign out and close the system?", "Sign out"):
            return
        auth_service.log_action(self.username, "Logged out")
        self.destroy()


class DoctorTab(ttk.Frame):
    """What a doctor sees: their own appointments and nothing else."""

    COLUMNS = [
        ("appointment_id", "ID", 70), ("date", "Date", 100), ("time", "Time", 70),
        ("patient_name", "Patient", 190), ("patient_age", "Age", 60),
        ("status", "Status", 100), ("grand_total", "Total", 90),
    ]

    def __init__(self, master, app):
        super().__init__(master, style="Card.TFrame", padding=14)
        self.app = app

        ttk.Label(self, text="My appointments", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="Only the visits assigned to you. Double-click a patient "
                             "to read their history.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        widgets.Toolbar(self, [
            ("Complete visit", self.complete, "primary"),
            ("Patient history", self.history, None),
            ("Refresh", self.refresh, None),
        ]).pack(fill="x")

        self.table = DataTable(self, self.COLUMNS, on_double_click=self.history)
        self.table.pack(fill="both", expand=True, pady=(10, 6))
        self.count = ttk.Label(self, text="", style="Muted.TLabel")
        self.count.pack(anchor="w")
        self.refresh()

    def refresh(self):
        doctor_id = self.app.linked_doctor_id
        if not doctor_id:
            self.count.configure(text="This account is not linked to a doctor record.")
            return
        try:
            rows = appointment_service.by_doctor(doctor_id, only_upcoming=False)
        except db.DatabaseError as e:
            widgets.error(str(e))
            return
        total = self.table.set_rows(rows, formatter=lambda r: dict(
            r, grand_total=widgets.money(r["grand_total"]) if r["grand_total"] else "-"))
        self.count.configure(text=f"{total} appointment(s)")

    def complete(self):
        from gui.appointments_tab import CompleteVisitWindow
        appointment_id = self.table.selected_value("appointment_id")
        if appointment_id is None:
            widgets.error("Choose an appointment from the list first.", "Nothing selected")
            return
        appointment = appointment_service.get(appointment_id)
        if appointment is None or appointment.status != "Booked":
            widgets.error("Only a booked visit can be completed.")
            return
        CompleteVisitWindow(self, self.app, appointment)
        self.refresh()
        self.app.refresh_dashboard()

    def history(self):
        row = self.table.selected()
        if row is None:
            widgets.error("Choose an appointment from the list first.", "Nothing selected")
            return
        self.app.show_patient_history(row["patient_id"], row["patient_name"])
