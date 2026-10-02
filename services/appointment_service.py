"""
appointment_service.py - Booking, cancelling, completing, and medical records.
Owner: Person 4
"""

from models.models import Appointment
from services import doctor_service, patient_service
from utils import database as db
from utils.validator import is_past, now_stamp, today, weekday_of


class AppointmentError(Exception):
    """Raised when an appointment cannot be created or changed."""


def book(patient_id, doctor_id, date_str, time_str, created_by, reason=""):
    """Create an appointment after every rule has been checked."""
    patient = patient_service.get_patient(patient_id)
    if patient is None:
        raise AppointmentError(f"No patient with ID {patient_id}.")

    doctor = doctor_service.get_doctor(doctor_id)
    if doctor is None:
        raise AppointmentError(f"No doctor with ID {doctor_id}.")
    if not doctor.is_active:
        raise AppointmentError(f"Dr. {doctor.name} is no longer taking appointments.")

    if is_past(date_str, time_str):
        raise AppointmentError("That time has already passed.")

    day = weekday_of(date_str)
    if not any(s.day_of_week == day for s in doctor_service.get_schedules(doctor_id)):
        raise AppointmentError(f"Dr. {doctor.name} does not work on {day}.")

    clash = db.query_one(
        """SELECT id FROM appointments
           WHERE doctor_id = ? AND date = ? AND time = ? AND status IN ('Booked', 'Completed')""",
        (doctor_id.upper(), date_str, time_str),
    )
    if clash:
        raise AppointmentError(
            f"Dr. {doctor.name} is already booked at {time_str} on {date_str} ({clash['id']})."
        )

    appt = Appointment(db.next_id("appointments", "A"), patient.id, doctor.id,
                       created_by, date_str, time_str, reason,
                       Appointment.BOOKED, doctor.fee, now_stamp())
    try:
        db.execute("INSERT INTO appointments (id, patient_id, doctor_id, created_by, `date`, `time`, reason, status, fee, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   appt.to_tuple())
    except db.IntegrityError:
        # The UNIQUE constraint is the real guarantee, even if the check above
        # was passed by two people at the same moment.
        raise AppointmentError("That slot was taken a moment ago. Please choose another.")
    return appt


def get(appointment_id):
    row = db.query_one("SELECT * FROM appointments WHERE id = ?", (appointment_id.upper(),))
    return Appointment.from_row(row) if row else None


def set_status(appointment_id, new_status):
    appt = get(appointment_id)
    if appt is None:
        raise AppointmentError(f"No appointment with ID {appointment_id}.")
    if appt.status == Appointment.COMPLETED:
        raise AppointmentError("A completed appointment cannot be changed.")
    if appt.status == new_status:
        raise AppointmentError(f"This appointment is already {new_status}.")
    db.execute("UPDATE appointments SET status = ? WHERE id = ?",
               (new_status, appointment_id.upper()))
    return get(appointment_id)


def cancel(appointment_id):
    return set_status(appointment_id, Appointment.CANCELLED)


def mark_no_show(appointment_id):
    return set_status(appointment_id, Appointment.NO_SHOW)


def complete(appointment_id):
    """Close a visit: status Completed, and the invoice is created."""
    from services import billing_service          # imported here to avoid a cycle

    appt = get(appointment_id)
    if appt is None:
        raise AppointmentError(f"No appointment with ID {appointment_id}.")
    if appt.status != Appointment.BOOKED:
        raise AppointmentError(f"Only a booked appointment can be completed "
                               f"(this one is {appt.status}).")

    db.execute("UPDATE appointments SET status = ? WHERE id = ?",
               (Appointment.COMPLETED, appt.id))
    invoice = billing_service.create_invoice(appt.id)
    return get(appt.id), invoice


# ----------------------------------------------------------- medical record
def add_record(appointment_id, symptoms, diagnosis, treatment, notes="", follow_up=""):
    appt = get(appointment_id)
    if appt is None:
        raise AppointmentError(f"No appointment with ID {appointment_id}.")
    if db.query_one("SELECT id FROM records WHERE appointment_id = ?", (appt.id,)):
        raise AppointmentError("This visit already has a medical record.")
    record_id = db.next_id("records", "R")
    db.execute("INSERT INTO records (id, appointment_id, symptoms, diagnosis, treatment, notes, follow_up_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (record_id, appt.id, symptoms, diagnosis, treatment, notes,
                follow_up or None, now_stamp()))
    return record_id


def get_record(appointment_id):
    return db.query_one("SELECT * FROM records WHERE appointment_id = ?",
                        (appointment_id.upper(),))


# ------------------------------------------------------------------ lists
def by_date(date_str):
    return db.query(
        "SELECT * FROM v_appointment_full WHERE date = ? ORDER BY time", (date_str,))


def by_doctor(doctor_id, only_upcoming=False):
    sql = "SELECT * FROM v_appointment_full WHERE doctor_id = ?"
    params = [doctor_id.upper()]
    if only_upcoming:
        sql += " AND date >= ?"
        params.append(today())
    return db.query(sql + " ORDER BY date, time", tuple(params))


def by_patient(patient_id):
    return db.query(
        "SELECT * FROM v_appointment_full WHERE patient_id = ? ORDER BY date DESC, time DESC",
        (patient_id.upper(),))


def by_status(status):
    return db.query(
        "SELECT * FROM v_appointment_full WHERE status = ? ORDER BY date, time", (status,))
