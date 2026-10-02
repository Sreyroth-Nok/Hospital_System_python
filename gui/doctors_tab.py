"""
doctors_tab.py - Departments, doctors and the weekly shifts that make
booking possible.
Owner: Person 3
"""

import tkinter as tk
from tkinter import ttk

from gui import widgets
from gui.widgets import DataTable, FormDialog, SearchBar, Toolbar
from services import auth_service, doctor_service
from services.doctor_service import DoctorError
from utils import database as db

DOCTOR_COLUMNS = [
    ("id", "ID", 70), ("name", "Name", 170), ("specialization", "Specialization", 150),
    ("department", "Department", 140), ("fee", "Fee", 80), ("phone", "Phone", 110),
    ("shifts", "Shifts", 170), ("state", "Status", 80),
]
DEPARTMENT_COLUMNS = [
    ("id", "ID", 70), ("name", "Name", 200), ("location", "Location", 200),
    ("phone", "Phone", 120), ("doctors", "Doctors", 80),
]
SHIFT_COLUMNS = [
    ("id", "ID", 70), ("day_of_week", "Day", 70), ("start_time", "From", 80),
    ("end_time", "To", 80), ("slot_minutes", "Slot (min)", 90),
]


class DoctorsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Card.TFrame", padding=14)
        self.app = app

        ttk.Label(self, text="Doctors & departments", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="A doctor with no shift cannot be booked, so add shifts "
                             "after registering one.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        inner = ttk.Notebook(self)
        inner.pack(fill="both", expand=True)

        self.doctors_page = ttk.Frame(inner, style="Card.TFrame", padding=10)
        self.departments_page = ttk.Frame(inner, style="Card.TFrame", padding=10)
        inner.add(self.doctors_page, text="Doctors")
        inner.add(self.departments_page, text="Departments")

        self._build_doctors()
        self._build_departments()
        self.refresh()

    # ------------------------------------------------------------ doctors
    def _build_doctors(self):
        bar = ttk.Frame(self.doctors_page, style="Card.TFrame")
        bar.pack(fill="x")
        Toolbar(bar, [
            ("Register doctor", self.register_doctor, "primary"),
            ("Edit", self.edit_doctor, None),
            ("Manage shifts", self.manage_shifts, None),
            ("Activate / deactivate", self.toggle_doctor, None),
            ("Refresh", self.refresh, None),
        ]).pack(side="left")
        SearchBar(bar, on_search=self.search_doctors, on_clear=self.refresh,
                  placeholder="Name, specialization or department").pack(side="right")

        self.doctor_table = DataTable(self.doctors_page, DOCTOR_COLUMNS,
                                      on_double_click=self.manage_shifts)
        self.doctor_table.pack(fill="both", expand=True, pady=(10, 0))

    def _build_departments(self):
        Toolbar(self.departments_page, [
            ("Add department", self.add_department, "primary"),
            ("Refresh", self.refresh, None),
        ]).pack(fill="x")
        self.department_table = DataTable(self.departments_page, DEPARTMENT_COLUMNS,
                                          height=10)
        self.department_table.pack(fill="both", expand=True, pady=(10, 0))

    # ------------------------------------------------------------ loading
    def refresh(self):
        try:
            self.show_doctors(doctor_service.get_all(active_only=False))
            self.show_departments()
        except db.DatabaseError as e:
            widgets.error(str(e))

    def show_doctors(self, doctors):
        departments = {d.id: d.name for d in doctor_service.get_departments()}
        self.doctor_table.set_rows(doctors, formatter=lambda d: {
            "id": d.id, "name": d.name, "specialization": d.specialization,
            "department": departments.get(d.department_id, d.department_id),
            "fee": widgets.money(d.fee), "phone": d.phone,
            "shifts": self._shift_summary(d.id),
            "state": "active" if d.is_active else "inactive",
        })

    @staticmethod
    def _shift_summary(doctor_id):
        shifts = doctor_service.get_schedules(doctor_id)
        if not shifts:
            return "no shift set"
        return ", ".join(sorted({s.day_of_week for s in shifts}))

    def show_departments(self):
        departments = doctor_service.get_departments()
        counts = {d.id: len(doctor_service.by_department(d.id)) for d in departments}
        self.department_table.set_rows(departments, formatter=lambda d: {
            "id": d.id, "name": d.name, "location": d.location or "-",
            "phone": d.phone or "-", "doctors": counts.get(d.id, 0),
        })

    def search_doctors(self, term):
        if not term:
            self.refresh()
            return
        try:
            self.show_doctors(doctor_service.search(term))
        except db.DatabaseError as e:
            widgets.error(str(e))

    def _selected_doctor(self):
        doctor_id = self.doctor_table.selected_value("id")
        if doctor_id is None:
            widgets.error("Choose a doctor from the list first.", "Nothing selected")
            return None
        return doctor_service.get_doctor(doctor_id)

    def _admin_only(self, what):
        if self.app.role != "admin":
            widgets.error(f"Only an admin can {what}.", "Not allowed")
            return False
        return True

    # ------------------------------------------------------------ actions
    def _department_options(self):
        return [f"{d.id} - {d.name}" for d in doctor_service.get_departments()]

    def register_doctor(self):
        if not self._admin_only("register a doctor"):
            return
        options = self._department_options()
        if not options:
            widgets.error("Add a department first.", "No department")
            return
        values = FormDialog.open(self, "Register a doctor", [
            {"key": "department", "label": "Department", "kind": "choice",
             "options": options},
            {"key": "name", "label": "Full name", "kind": "text"},
            {"key": "gender", "label": "Gender", "kind": "gender"},
            {"key": "age", "label": "Age", "kind": "int", "minimum": 20, "maximum": 90},
            {"key": "phone", "label": "Phone", "kind": "phone"},
            {"key": "specialization", "label": "Specialization", "kind": "text"},
            {"key": "fee", "label": "Consultation fee", "kind": "float"},
        ], submit_label="Register")
        if not values:
            return
        try:
            doctor = doctor_service.add_doctor(
                values["department"].split(" - ")[0], values["name"], values["gender"],
                values["age"], values["phone"], values["specialization"], values["fee"])
        except (DoctorError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Registered doctor {doctor.id}")
        self.refresh()
        if widgets.ask(f"Dr. {doctor.name} saved as {doctor.id}.\n"
                       "Add weekly shifts now so the doctor can be booked?"):
            ShiftWindow(self, self.app, doctor)
            self.refresh()

    def edit_doctor(self):
        if not self._admin_only("edit a doctor"):
            return
        doctor = self._selected_doctor()
        if doctor is None:
            return
        values = FormDialog.open(self, f"Edit {doctor.id}", [
            {"key": "name", "label": "Full name", "kind": "text", "default": doctor.name},
            {"key": "phone", "label": "Phone", "kind": "phone", "default": doctor.phone},
            {"key": "specialization", "label": "Specialization", "kind": "text",
             "default": doctor.specialization},
            {"key": "fee", "label": "Consultation fee", "kind": "float",
             "default": doctor.fee},
        ], submit_label="Save changes")
        if not values:
            return
        try:
            doctor_service.update_doctor(doctor.id, **values)
        except (DoctorError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Updated doctor {doctor.id}")
        widgets.info("Doctor updated. Invoices already issued keep their old fee.")
        self.refresh()

    def toggle_doctor(self):
        if not self._admin_only("change a doctor's status"):
            return
        doctor = self._selected_doctor()
        if doctor is None:
            return
        going_active = not doctor.is_active
        word = "activate" if going_active else "deactivate"
        if not widgets.ask(f"{word.title()} Dr. {doctor.name}?\n"
                           "History is always kept either way."):
            return
        try:
            doctor_service.set_active(doctor.id, going_active)
        except (DoctorError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"{word.title()}d doctor {doctor.id}")
        self.refresh()

    def manage_shifts(self):
        doctor = self._selected_doctor()
        if doctor is None:
            return
        ShiftWindow(self, self.app, doctor)
        self.refresh()

    def add_department(self):
        if not self._admin_only("add a department"):
            return
        values = FormDialog.open(self, "Add a department", [
            {"key": "name", "label": "Department name", "kind": "text"},
            {"key": "location", "label": "Location", "kind": "text", "required": False},
            {"key": "phone", "label": "Phone", "kind": "phone", "required": False},
        ], submit_label="Add")
        if not values:
            return
        try:
            department = doctor_service.add_department(**values)
        except (DoctorError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        widgets.info(f"{department.name} added as {department.id}.")
        self.refresh()


class ShiftWindow(tk.Toplevel):
    """The weekly shifts of one doctor, which decide the free slots."""

    def __init__(self, master, app, doctor):
        super().__init__(master)
        self.app = app
        self.doctor = doctor
        self.title(f"Shifts - Dr. {doctor.name} ({doctor.id})")
        self.configure(background=widgets.SURFACE)
        self.transient(master)

        frame = ttk.Frame(self, style="Card.TFrame", padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Weekly shifts for Dr. {doctor.name}",
                  style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Each shift is cut into slots of the length you choose.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        Toolbar(frame, [
            ("Add shift", self.add_shift, "primary"),
            ("Delete shift", self.delete_shift, "danger"),
        ]).pack(fill="x")

        self.table = DataTable(frame, SHIFT_COLUMNS, height=8)
        self.table.pack(fill="both", expand=True, pady=(10, 10))
        ttk.Button(frame, text="Close", command=self.destroy).pack(anchor="e")

        self.refresh()
        self.grab_set()
        master.wait_window(self)

    def refresh(self):
        try:
            self.table.set_rows(doctor_service.get_schedules(self.doctor.id))
        except db.DatabaseError as e:
            widgets.error(str(e))

    def add_shift(self):
        values = FormDialog.open(self, "Add a shift", [
            {"key": "day_of_week", "label": "Day", "kind": "day",
             "options": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]},
            {"key": "start_time", "label": "Start time (HH:MM)", "kind": "time",
             "default": "08:00"},
            {"key": "end_time", "label": "End time (HH:MM)", "kind": "time",
             "default": "12:00"},
            {"key": "slot_minutes", "label": "Slot length in minutes", "kind": "int",
             "minimum": 5, "maximum": 120, "default": 30},
        ], submit_label="Add shift")
        if not values:
            return
        try:
            doctor_service.add_schedule(self.doctor.id, **values)
        except (DoctorError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        self.refresh()

    def delete_shift(self):
        shift_id = self.table.selected_value("id")
        if shift_id is None:
            widgets.error("Choose a shift first.", "Nothing selected")
            return
        if not widgets.ask("Delete this shift? Appointments already booked are kept."):
            return
        try:
            doctor_service.delete_schedule(shift_id)
        except (DoctorError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        self.refresh()
