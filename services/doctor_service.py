"""
doctor_service.py - Departments, doctors, weekly shifts and free slots.
Owner: Person 3
"""

from datetime import datetime, timedelta

from models.models import Department, Doctor, Schedule
from utils import database as db
from utils.validator import DATE_FMT, TIME_FMT, weekday_of


class DoctorError(Exception):
    """Raised when a doctor or department operation cannot be completed."""


# ------------------------------------------------------------ departments
def add_department(name, location="", phone=""):
    dept = Department(db.next_id("departments", "DP", 2), name, location, phone)
    try:
        db.execute("INSERT INTO departments (id, name, location, phone)"
                   " VALUES (?, ?, ?, ?)", dept.to_tuple())
    except db.IntegrityError:
        raise DoctorError(f"A department called '{name}' already exists.")
    return dept


def get_departments():
    rows = db.query("SELECT * FROM departments ORDER BY id")
    return [Department(r["id"], r["name"], r["location"], r["phone"]) for r in rows]


def get_department(dept_id):
    row = db.query_one("SELECT * FROM departments WHERE id = ?", (dept_id.upper(),))
    return Department(row["id"], row["name"], row["location"], row["phone"]) if row else None


def delete_department(dept_id):
    row = db.query_one("SELECT COUNT(*) AS c FROM doctors WHERE department_id = ?",
                       (dept_id.upper(),))
    if row["c"]:
        raise DoctorError(f"{row['c']} doctor(s) belong to this department.")
    db.execute("DELETE FROM departments WHERE id = ?", (dept_id.upper(),))


# ---------------------------------------------------------------- doctors
def add_doctor(department_id, name, gender, age, phone, specialization, fee):
    if get_department(department_id) is None:
        raise DoctorError(f"No department with ID {department_id}.")
    doctor = Doctor(db.next_id("doctors", "D"), department_id.upper(), name,
                    gender, age, phone, specialization, fee, 1)
    db.execute("INSERT INTO doctors (id, department_id, name, gender, age, phone,"
               " specialization, fee, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               doctor.to_tuple())
    return doctor


def get_doctor(doctor_id):
    row = db.query_one("SELECT * FROM doctors WHERE id = ?", (doctor_id.upper(),))
    return Doctor.from_row(row) if row else None


def get_all(active_only=True):
    sql = "SELECT * FROM doctors"
    if active_only:
        sql += " WHERE is_active = 1"
    return [Doctor.from_row(r) for r in db.query(sql + " ORDER BY id")]


def search(term):
    like = f"%{term}%"
    rows = db.query(
        """SELECT d.* FROM doctors d
           JOIN departments dp ON dp.id = d.department_id
           WHERE d.id LIKE ? OR d.name LIKE ? OR d.specialization LIKE ? OR dp.name LIKE ?
           ORDER BY d.name""",
        (like.upper(), like, like, like),
    )
    return [Doctor.from_row(r) for r in rows]


def by_department(dept_id):
    rows = db.query(
        "SELECT * FROM doctors WHERE department_id = ? AND is_active = 1 ORDER BY id",
        (dept_id.upper(),),
    )
    return [Doctor.from_row(r) for r in rows]


def update_doctor(doctor_id, **fields):
    allowed = {"name", "gender", "age", "phone", "specialization", "fee", "department_id"}
    changes = {k: v for k, v in fields.items() if k in allowed and v not in (None, "")}
    if not changes:
        raise DoctorError("Nothing to update.")
    if get_doctor(doctor_id) is None:
        raise DoctorError(f"No doctor with ID {doctor_id}.")
    sets = ", ".join(f"{k} = ?" for k in changes)
    db.execute(f"UPDATE doctors SET {sets} WHERE id = ?",
               tuple(changes.values()) + (doctor_id.upper(),))
    return get_doctor(doctor_id)


def set_active(doctor_id, active):
    """Doctors are deactivated, never deleted, so old appointments stay valid."""
    if get_doctor(doctor_id) is None:
        raise DoctorError(f"No doctor with ID {doctor_id}.")
    db.execute("UPDATE doctors SET is_active = ? WHERE id = ?",
               (1 if active else 0, doctor_id.upper()))


# -------------------------------------------------------------- schedules
def add_schedule(doctor_id, day_of_week, start_time, end_time, slot_minutes=30):
    if get_doctor(doctor_id) is None:
        raise DoctorError(f"No doctor with ID {doctor_id}.")
    if start_time >= end_time:
        raise DoctorError("The shift must end after it starts.")
    for existing in get_schedules(doctor_id):
        if existing.day_of_week == day_of_week and \
           start_time < existing.end_time and existing.start_time < end_time:
            raise DoctorError(
                f"This overlaps the existing {day_of_week} shift "
                f"{existing.start_time}-{existing.end_time}."
            )
    schedule = Schedule(db.next_id("schedules", "S"), doctor_id.upper(),
                        day_of_week, start_time, end_time, slot_minutes)
    try:
        db.execute("INSERT INTO schedules (id, doctor_id, day_of_week, start_time,"
                   " end_time, slot_minutes) VALUES (?, ?, ?, ?, ?, ?)",
                   schedule.to_tuple())
    except db.IntegrityError:
        raise DoctorError("That shift already exists for this doctor.")
    return schedule


def get_schedules(doctor_id):
    rows = db.query("SELECT * FROM schedules WHERE doctor_id = ? ORDER BY id",
                    (doctor_id.upper(),))
    return [Schedule(r["id"], r["doctor_id"], r["day_of_week"], r["start_time"],
                     r["end_time"], r["slot_minutes"]) for r in rows]


def delete_schedule(schedule_id):
    changed = db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id.upper(),))
    if not changed:
        raise DoctorError(f"No shift with ID {schedule_id}.")


def free_slots(doctor_id, date_str):
    """Every free time on a date: the shift cut into slots, minus what is booked.

    Raises DoctorError when the doctor does not work that weekday, so the
    caller can say why rather than showing an empty list.
    """
    doctor = get_doctor(doctor_id)
    if doctor is None:
        raise DoctorError(f"No doctor with ID {doctor_id}.")

    day = weekday_of(date_str)
    shifts = [s for s in get_schedules(doctor_id) if s.day_of_week == day]
    if not shifts:
        raise DoctorError(f"Dr. {doctor.name} does not work on {day}.")

    taken = {r["time"] for r in db.query(
        """SELECT time FROM appointments
           WHERE doctor_id = ? AND date = ? AND status IN ('Booked', 'Completed')""",
        (doctor_id.upper(), date_str))}

    slots = []
    now = datetime.now()
    for shift in shifts:
        cursor = datetime.strptime(f"{date_str} {shift.start_time}", f"{DATE_FMT} {TIME_FMT}")
        finish = datetime.strptime(f"{date_str} {shift.end_time}", f"{DATE_FMT} {TIME_FMT}")
        while cursor < finish:
            label = cursor.strftime(TIME_FMT)
            if label not in taken and cursor > now:
                slots.append(label)
            cursor += timedelta(minutes=shift.slot_minutes)
    return sorted(slots)
