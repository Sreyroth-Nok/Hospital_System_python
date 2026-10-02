"""
patient_service.py - Everything the system does with patients.
Owner: Person 2
"""

from models.models import Patient
from utils import database as db
from utils.validator import today


class PatientError(Exception):
    """Raised when a patient operation cannot be completed."""


def add_patient(name, gender, age, phone, address="", blood_type="", allergies=""):
    """Register a patient and return the new Patient object."""
    patient = Patient(db.next_id("patients", "P"), name, gender, age, phone,
                      address, blood_type, allergies, today())
    db.execute(
        "INSERT INTO patients (id, name, gender, age, phone, address, blood_type,"
        " allergies, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        patient.to_tuple(),
    )
    return patient


def get_patient(patient_id):
    row = db.query_one("SELECT * FROM patients WHERE id = ?", (patient_id.upper(),))
    return Patient.from_row(row) if row else None


def get_all():
    return [Patient.from_row(r) for r in db.query("SELECT * FROM patients ORDER BY id")]


def search(term):
    """Search by ID, part of the name, or phone."""
    like = f"%{term}%"
    rows = db.query(
        "SELECT * FROM patients WHERE id LIKE ? OR name LIKE ? OR phone LIKE ? ORDER BY name",
        (like.upper(), like, like),
    )
    return [Patient.from_row(r) for r in rows]


def update_patient(patient_id, **fields):
    """Update any stored field except the ID."""
    allowed = {"name", "gender", "age", "phone", "address", "blood_type", "allergies"}
    changes = {k: v for k, v in fields.items() if k in allowed and v not in (None, "")}
    if not changes:
        raise PatientError("Nothing to update.")
    if get_patient(patient_id) is None:
        raise PatientError(f"No patient with ID {patient_id}.")
    sets = ", ".join(f"{k} = ?" for k in changes)
    db.execute(f"UPDATE patients SET {sets} WHERE id = ?",
               tuple(changes.values()) + (patient_id.upper(),))
    return get_patient(patient_id)


def appointment_count(patient_id):
    row = db.query_one(
        "SELECT COUNT(*) AS c FROM appointments WHERE patient_id = ?",
        (patient_id.upper(),),
    )
    return row["c"]


def delete_patient(patient_id):
    """Delete only when the patient has no history at all."""
    if get_patient(patient_id) is None:
        raise PatientError(f"No patient with ID {patient_id}.")
    count = appointment_count(patient_id)
    if count:
        raise PatientError(
            f"This patient has {count} appointment(s) on record and cannot be deleted."
        )
    db.execute("DELETE FROM patients WHERE id = ?", (patient_id.upper(),))


def visit_history(patient_id):
    """Every visit for one patient, newest first."""
    return db.query(
        """SELECT a.id, a.date, a.time, a.status, d.name AS doctor_name,
                  d.specialization, r.diagnosis, i.grand_total, i.payment_status
           FROM appointments a
           JOIN doctors d ON d.id = a.doctor_id
           LEFT JOIN records  r ON r.appointment_id = a.id
           LEFT JOIN invoices i ON i.appointment_id = a.id
           WHERE a.patient_id = ?
           ORDER BY a.date DESC, a.time DESC""",
        (patient_id.upper(),),
    )
