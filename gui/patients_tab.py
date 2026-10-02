"""
patients_tab.py - Register, find, update and remove patients.
Owner: Person 2
"""

from tkinter import ttk

from gui import widgets
from gui.widgets import DataTable, FormDialog, SearchBar, Toolbar
from services import auth_service, patient_service
from services.patient_service import PatientError
from utils import database as db

COLUMNS = [
    ("id", "ID", 70), ("name", "Name", 180), ("gender", "Sex", 50),
    ("age", "Age", 50), ("phone", "Phone", 110), ("blood_type", "Blood", 60),
    ("allergies", "Allergies", 150), ("address", "Address", 190),
]


def patient_fields(patient=None, required=True):
    """The same form is used to register and to update."""
    return [
        {"key": "name", "label": "Full name", "kind": "text",
         "default": patient.name if patient else "", "required": required},
        {"key": "gender", "label": "Gender", "kind": "gender",
         "default": patient.gender if patient else "", "required": required},
        {"key": "age", "label": "Age", "kind": "int", "minimum": 0, "maximum": 120,
         "default": patient.age if patient else "", "required": required},
        {"key": "phone", "label": "Phone", "kind": "phone",
         "default": patient.phone if patient else "", "required": required},
        {"key": "address", "label": "Address", "kind": "text",
         "default": patient.address if patient else "", "required": False},
        {"key": "blood_type", "label": "Blood type", "kind": "text",
         "default": patient.blood_type if patient else "", "required": False},
        {"key": "allergies", "label": "Allergies", "kind": "text",
         "default": patient.allergies if patient else "", "required": False},
    ]


class PatientsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Card.TFrame", padding=14)
        self.app = app

        ttk.Label(self, text="Patients", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="Double-click a row to see that patient's visit history.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(fill="x")
        Toolbar(bar, [
            ("Register patient", self.register, "primary"),
            ("Update", self.update, None),
            ("Visit history", self.history, None),
            ("Delete", self.delete, "danger"),
            ("Refresh", self.refresh, None),
        ]).pack(side="left")
        SearchBar(bar, on_search=self.search, on_clear=self.refresh,
                  placeholder="ID, name or phone").pack(side="right")

        self.table = DataTable(self, COLUMNS, on_double_click=self.history)
        self.table.pack(fill="both", expand=True, pady=(10, 6))

        self.count = ttk.Label(self, text="", style="Muted.TLabel")
        self.count.pack(anchor="w")
        self.refresh()

    # ------------------------------------------------------------ loading
    def refresh(self):
        try:
            self.show(patient_service.get_all())
        except db.DatabaseError as e:
            widgets.error(str(e))

    def search(self, term):
        if not term:
            self.refresh()
            return
        try:
            found = patient_service.search(term)
        except db.DatabaseError as e:
            widgets.error(str(e))
            return
        self.show(found)
        if not found:
            self.count.configure(text=f"No patient matches '{term}'.")

    def show(self, patients):
        total = self.table.set_rows(patients, formatter=lambda p: {
            "id": p.id, "name": p.name, "gender": p.gender, "age": p.age,
            "phone": p.phone, "blood_type": p.blood_type,
            "allergies": p.allergies or "-", "address": p.address or "-",
        })
        self.count.configure(text=f"{total} patient(s)")

    def _selected(self):
        patient = self.table.selected()
        if patient is None:
            widgets.error("Choose a patient from the list first.", "Nothing selected")
        return patient

    # ------------------------------------------------------------ actions
    def register(self):
        values = FormDialog.open(self, "Register a patient", patient_fields(),
                                 submit_label="Register")
        if not values:
            return
        try:
            patient = patient_service.add_patient(**values)
        except (PatientError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Registered patient {patient.id}")
        widgets.info(f"{patient.name} registered as {patient.id}.")
        self.refresh()
        self.app.refresh_dashboard()

    def update(self):
        patient = self._selected()
        if patient is None:
            return
        values = FormDialog.open(self, f"Update {patient.id}",
                                 patient_fields(patient), submit_label="Save changes")
        if not values:
            return
        try:
            patient_service.update_patient(patient.id, **values)
        except (PatientError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Updated patient {patient.id}")
        widgets.info("Patient updated.")
        self.refresh()

    def delete(self):
        patient = self._selected()
        if patient is None:
            return
        if self.app.role != "admin":
            widgets.error("Only an admin can delete a patient.", "Not allowed")
            return
        if not widgets.ask(f"Delete {patient.name} ({patient.id})?\n"
                           "This cannot be undone."):
            return
        try:
            patient_service.delete_patient(patient.id)
        except (PatientError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Deleted patient {patient.id}")
        widgets.info("Patient deleted.")
        self.refresh()
        self.app.refresh_dashboard()

    def history(self):
        patient = self.table.selected()
        if patient is None:
            widgets.error("Choose a patient from the list first.", "Nothing selected")
            return
        self.app.show_patient_history(patient.id, patient.name)
