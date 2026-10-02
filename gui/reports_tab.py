"""
reports_tab.py - Every report, with a CSV export button.
Owner: Person 4
"""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

from gui import widgets
from gui.widgets import DataTable
from services import auth_service, report_service
from utils import database as db
from utils.validator import DATE_FMT, today

REPORTS = [
    "Today's appointment sheet",
    "Income by doctor",
    "Income by department",
    "Busiest doctors",
    "Busiest weekdays",
    "Appointment status summary",
    "Audit log",
]

LAYOUTS = {
    "Today's appointment sheet": [
        ("time", "Time", 70), ("appointment_id", "ID", 70),
        ("patient_name", "Patient", 180), ("doctor_name", "Doctor", 180),
        ("department", "Department", 140), ("status", "Status", 90),
        ("grand_total", "Total", 90)],
    "Income by doctor": [
        ("doctor_name", "Doctor", 200), ("department", "Department", 160),
        ("visits", "Visits", 80), ("income", "Income", 110)],
    "Income by department": [
        ("department", "Department", 220), ("visits", "Visits", 80),
        ("income", "Income", 110)],
    "Busiest doctors": [
        ("doctor_name", "Doctor", 220), ("specialization", "Specialization", 180),
        ("visits", "Visits", 80)],
    "Busiest weekdays": [("weekday", "Weekday", 160), ("visits", "Visits", 80)],
    "Appointment status summary": [("status", "Status", 160), ("total", "Count", 80)],
    "Audit log": [("timestamp", "When", 150), ("username", "User", 140),
                  ("action", "Action", 360)],
}

FILENAMES = {
    "Today's appointment sheet": "daily_sheet",
    "Income by doctor": "income_by_doctor",
    "Income by department": "income_by_department",
    "Busiest doctors": "busiest_doctors",
    "Busiest weekdays": "busiest_weekdays",
    "Appointment status summary": "status_summary",
    "Audit log": "audit_log",
}


class ReportsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Card.TFrame", padding=14)
        self.app = app
        self.rows = []
        self.table = None

        ttk.Label(self, text="Reports", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="Income reports cover the date range you choose "
                             "and can be exported to CSV.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        controls = ttk.Frame(self, style="Card.TFrame")
        controls.pack(fill="x", pady=(0, 10))

        self.choice = tk.StringVar(value=REPORTS[0])
        chooser = ttk.Combobox(controls, textvariable=self.choice, state="readonly",
                               width=28, values=self._available_reports())
        chooser.pack(side="left", padx=(0, 10), pady=8)
        chooser.bind("<<ComboboxSelected>>", lambda event: self.run())

        month_ago = (datetime.now() - timedelta(days=30)).strftime(DATE_FMT)
        self.start = tk.StringVar(value=month_ago)
        self.end = tk.StringVar(value=today())
        ttk.Label(controls, text="From", style="Muted.TLabel").pack(side="left")
        ttk.Entry(controls, textvariable=self.start, width=12).pack(side="left", padx=4)
        ttk.Label(controls, text="To", style="Muted.TLabel").pack(side="left")
        ttk.Entry(controls, textvariable=self.end, width=12).pack(side="left", padx=4)

        ttk.Button(controls, text="Run", command=self.run,
                   style="Primary.TButton").pack(side="left", padx=(10, 0))
        ttk.Button(controls, text="Export to CSV",
                   command=self.export).pack(side="left", padx=(8, 0))

        self.holder = ttk.Frame(self, style="Card.TFrame")
        self.holder.pack(fill="both", expand=True)
        self.summary = ttk.Label(self, text="", style="Muted.TLabel")
        self.summary.pack(anchor="w", pady=(6, 0))

        self.run()

    def _available_reports(self):
        if self.app.role == "admin":
            return REPORTS
        return [r for r in REPORTS if r not in ("Income by doctor",
                                                "Income by department", "Audit log")]

    # --------------------------------------------------------------- run
    def run(self):
        name = self.choice.get()
        try:
            self.rows = self._fetch(name)
        except (ValueError, db.DatabaseError) as e:
            widgets.error(str(e))
            return

        for child in self.holder.winfo_children():
            child.destroy()
        self.table = DataTable(self.holder, LAYOUTS[name])
        self.table.pack(fill="both", expand=True)
        self.table.set_rows(self.rows, formatter=self._format)
        self.summary.configure(text=self._summary_line(name))

    def _fetch(self, name):
        if name == "Today's appointment sheet":
            return report_service.daily_sheet(today())
        if name in ("Income by doctor", "Income by department"):
            if self.app.role != "admin":
                raise ValueError("Only an admin can see income reports.")
            start, end = self.start.get().strip(), self.end.get().strip()
            if name == "Income by doctor":
                return report_service.income_by_doctor(start, end)
            return report_service.income_by_department(start, end)
        if name == "Busiest doctors":
            return report_service.busiest_doctors()
        if name == "Busiest weekdays":
            return report_service.busiest_weekdays()
        if name == "Appointment status summary":
            return report_service.status_summary()
        if self.app.role != "admin":
            raise ValueError("Only an admin can read the audit log.")
        return auth_service.read_audit_log(200)

    @staticmethod
    def _format(row):
        formatted = dict(row)
        for key in ("income", "grand_total"):
            if key in formatted:
                formatted[key] = widgets.money(formatted[key]) if formatted[key] else "-"
        return formatted

    def _summary_line(self, name):
        if not self.rows:
            return "Nothing to show for that choice."
        if name in ("Income by doctor", "Income by department"):
            total = sum(float(r["income"] or 0) for r in self.rows)
            return (f"{len(self.rows)} row(s), {widgets.money(total)} collected "
                    f"between {self.start.get()} and {self.end.get()}")
        return f"{len(self.rows)} row(s)"

    def export(self):
        if not self.rows:
            widgets.error("Run a report first.", "Nothing to export")
            return
        try:
            path = report_service.export_csv(self.rows, FILENAMES[self.choice.get()])
        except (ValueError, OSError) as e:
            widgets.error(str(e))
            return
        widgets.info(f"Saved to\n{path}")
