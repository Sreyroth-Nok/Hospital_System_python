"""
seed_data.py - Fill the database with realistic demo data for testing and the demo.
Owner: Person 2

Run:  python seed_data.py
"""

import random
from datetime import datetime, timedelta

from services import appointment_service, auth_service, billing_service, doctor_service, patient_service
from utils import database as db
from utils.validator import DATE_FMT

random.seed(7)          # same demo data every run, so screenshots stay consistent

DEPARTMENTS = [
    ("Cardiology", "Building A, Floor 2", "023900101"),
    ("Pediatrics", "Building A, Floor 1", "023900102"),
    ("General Medicine", "Building B, Floor 1", "023900103"),
]

DOCTORS = [
    ("Chan Ratha", "F", 44, "012345001", "Cardiology", 35.0, 0),
    ("Sok Piseth", "M", 51, "012345002", "Cardiac Surgery", 45.0, 0),
    ("Meas Sophea", "F", 38, "012345003", "Pediatrics", 25.0, 1),
    ("Kim Dara", "M", 33, "012345004", "Child Nutrition", 22.0, 1),
    ("Nou Vanna", "F", 47, "012345005", "General Practice", 20.0, 2),
    ("Heng Bunthy", "M", 29, "012345006", "Family Medicine", 18.0, 2),
]

SHIFTS = [
    ("Mon", "08:00", "12:00"), ("Tue", "08:00", "12:00"),
    ("Wed", "13:00", "17:00"), ("Thu", "08:00", "12:00"),
    ("Fri", "13:00", "17:00"),
]

FIRST = ["Sok", "Chan", "Meas", "Kim", "Nou", "Heng", "Pich", "Sam", "Ly", "Tep",
         "Vong", "Chea", "Mao", "Sar", "Hout", "Eng", "Long", "Chhun", "Neang", "Rith"]
LAST = ["Dara", "Sophea", "Vanna", "Bunthy", "Piseth", "Sreymom", "Kosal", "Chenda",
        "Sina", "Rady", "Makara", "Vibol", "Sokha", "Phalla", "Nita", "Visal",
        "Theary", "Samnang", "Chantha", "Leakhena"]

BLOOD = ["A+", "B+", "O+", "AB+", "A-", "O-"]
ALLERGIES = ["", "", "", "Penicillin", "Dust", "Seafood", "Pollen"]

MEDICINES = [
    ("Paracetamol 500mg", "Painkiller", "tablet", 0.10, 500, 50, "2027-06-30"),
    ("Amoxicillin 250mg", "Antibiotic", "capsule", 0.35, 200, 40, "2027-03-31"),
    ("Ibuprofen 400mg", "Painkiller", "tablet", 0.15, 300, 50, "2027-01-31"),
    ("ORS sachet", "Rehydration", "sachet", 0.25, 40, 30, "2026-12-31"),
    ("Amlodipine 5mg", "Blood pressure", "tablet", 0.30, 120, 30, "2027-08-31"),
    ("Cough syrup 100ml", "Respiratory", "bottle", 2.50, 25, 20, "2026-11-30"),
]

SYMPTOMS = ["Chest pain and shortness of breath", "Fever for three days",
            "Persistent cough", "Headache and dizziness", "Stomach pain",
            "High blood pressure at home reading"]
DIAGNOSES = ["Mild hypertension", "Viral fever", "Bronchitis", "Migraine",
             "Gastritis", "Stable angina"]
TREATMENTS = ["Rest and medication", "Antibiotic course for 5 days",
              "Fluids and monitoring", "Follow-up in two weeks",
              "Diet advice and medication"]


def clear_all():
    """Empty every table so the seed can be run again from scratch."""
    # Order matters: a child row is always removed before its parent.
    db.execute("DELETE FROM audit_log WHERE username <> 'admin'")
    db.execute("DELETE FROM users WHERE username <> 'admin'")
    for table in ("audit_log", "prescriptions", "records", "invoices",
                  "appointments", "schedules", "doctors", "departments",
                  "medicines", "patients"):
        db.execute(f"DELETE FROM {table}")


def run():
    import sys
    if "--sqlite" in sys.argv:
        db.set_backend("sqlite")
    elif "--mysql" in sys.argv:
        db.set_backend("mysql")

    db.init_db()
    auth_service.ensure_default_admin()
    clear_all()
    print("Seeding demo data...")

    departments = [doctor_service.add_department(*d) for d in DEPARTMENTS]
    print(f"  {len(departments)} departments")

    doctors = []
    for name, gender, age, phone, spec, fee, dept_index in DOCTORS:
        doctor = doctor_service.add_doctor(departments[dept_index].id, name, gender,
                                           age, phone, spec, fee)
        doctors.append(doctor)
        for day, start, end in random.sample(SHIFTS, 3):
            doctor_service.add_schedule(doctor.id, day, start, end, 30)
    print(f"  {len(doctors)} doctors with 3 shifts each")

    patients = []
    for i in range(20):
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        age = random.choice([2, 4, 7, 15, 22, 28, 31, 35, 42, 48, 55, 62, 68, 73])
        patients.append(patient_service.add_patient(
            name, random.choice("MF"), age, f"0966{random.randint(100000, 999999)}",
            f"Street {random.randint(1, 300)}, Phnom Penh",
            random.choice(BLOOD), random.choice(ALLERGIES)))
    print(f"  {len(patients)} patients")

    for med in MEDICINES:
        billing_service.add_medicine(*med)
    print(f"  {len(MEDICINES)} medicines")

    auth_service.create_user("reception1", "recep123", "receptionist")
    auth_service.create_user("drratha", "doctor123", "doctor", doctors[0].id)
    print("  3 user accounts (admin, reception1, drratha)")

    # --- appointments across the last three weeks and the next two ---
    booked = completed = 0
    start = datetime.now() - timedelta(days=21)
    for offset in range(35):
        day = start + timedelta(days=offset)
        date_str = day.strftime(DATE_FMT)
        in_past = day.date() < datetime.now().date()
        for _ in range(random.randint(2, 6)):
            doctor = random.choice(doctors)
            patient = random.choice(patients)
            shifts = [s for s in doctor_service.get_schedules(doctor.id)
                      if s.day_of_week == day.strftime("%a")]
            if not shifts:
                continue
            shift = shifts[0]
            hour, minute = map(int, shift.start_time.split(":"))
            slot = (datetime(2000, 1, 1, hour, minute)
                    + timedelta(minutes=30 * random.randint(0, 7))).strftime("%H:%M")
            try:
                appt = _force_book(patient.id, doctor.id, date_str, slot)
            except Exception:
                continue
            booked += 1
            if in_past and random.random() < 0.8:
                _force_complete(appt, patient, doctor, random.random() < 0.7)
                completed += 1
    print(f"  {booked} appointments, {completed} of them completed with invoices")
    print("\nDone. Log in as admin / admin123")


def _force_book(patient_id, doctor_id, date_str, time_str):
    """Insert an appointment directly, so past dates can be seeded for reports."""
    from models.models import Appointment
    from utils.validator import now_stamp
    doctor = doctor_service.get_doctor(doctor_id)
    appt = Appointment(db.next_id("appointments", "A"), patient_id, doctor_id,
                       "admin", date_str, time_str, "Consultation",
                       Appointment.BOOKED, doctor.fee, now_stamp())
    db.execute("INSERT INTO appointments (id, patient_id, doctor_id, created_by, `date`, `time`, reason, status, fee, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               appt.to_tuple())
    return appt


def _force_complete(appt, patient, doctor, pay):
    """Complete a seeded visit: record, maybe a prescription, invoice, payment."""
    db.execute("UPDATE appointments SET status = 'Completed' WHERE id = ?", (appt.id,))
    record_id = appointment_service.add_record(
        appt.id, random.choice(SYMPTOMS), random.choice(DIAGNOSES),
        random.choice(TREATMENTS))
    invoice = billing_service.create_invoice(appt.id)
    if random.random() < 0.6:
        med = random.choice(billing_service.get_medicines())
        try:
            billing_service.prescribe(record_id, med.id, random.randint(5, 20),
                                      "1 after meals")
        except Exception:
            pass
    if pay:
        billing_service.mark_paid(invoice.id, random.choice(["Cash", "Card", "ABA"]))


if __name__ == "__main__":
    run()
