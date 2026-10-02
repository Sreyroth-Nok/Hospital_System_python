"""
main.py - Hospital Appointment & Patient Management System.
Owner: Person 1

Run:    python main.py
Login:  admin / admin123   (or reception1 / recep123, drratha / doctor123 after seeding)
"""

import sys

from services import (appointment_service, auth_service, billing_service,
                      doctor_service, patient_service, report_service)
from services.appointment_service import AppointmentError
from services.billing_service import BillingError
from services.doctor_service import DoctorError
from services.patient_service import PatientError
from utils import database as db, receipt
from utils.database import DatabaseError
from utils.validator import (confirm, input_choice, input_date, input_day,
                             input_float, input_gender, input_int, input_phone,
                             input_text, input_time, today)

W = 66
user = None                     # the row of whoever is logged in


# ------------------------------------------------------------- presentation
def banner(title):
    print("\n" + "=" * W)
    print(title.center(W))
    print("=" * W)


def section(title):
    print("\n" + "-" * W)
    print(f" {title}")
    print("-" * W)


def ok(message):
    print(f"  [ok] {message}")


def warn(message):
    print(f"  [!] {message}")


def table(rows, columns, headers=None, widths=None):
    """Print a list of sqlite3.Row or objects as an aligned table."""
    if not rows:
        warn("Nothing to show.")
        return
    headers = headers or columns
    widths = widths or [max(len(str(h)), 14) for h in headers]
    line = "  ".join(f"{h:<{w}}" for h, w in zip(headers, widths))
    print("  " + line)
    print("  " + "-" * len(line))
    for row in rows:
        cells = []
        for col, width in zip(columns, widths):
            value = row[col] if not hasattr(row, col) else getattr(row, col)
            value = "" if value is None else str(value)
            cells.append(f"{value[:width]:<{width}}")
        print("  " + "  ".join(cells))
    print(f"  ({len(rows)} row(s))")


def pause():
    input("\n  Press Enter to continue...")


# -------------------------------------------------------------------- login
def login_screen():
    banner("HOSPITAL APPOINTMENT & PATIENT MANAGEMENT SYSTEM")
    for attempt in range(3):
        username = input_text("  Username : ")
        password = input_text("  Password : ")
        row = auth_service.login(username, password)
        if row:
            ok(f"Welcome, {row['username']} ({row['role']})")
            return row
        warn(f"Wrong username or password. {2 - attempt} attempt(s) left.")
    return None


def allowed(*roles):
    return user["role"] in roles


# ----------------------------------------------------------------- patients
def patient_menu():
    while True:
        section("PATIENT MANAGEMENT")
        print("   1. Register a patient        4. Update a patient")
        print("   2. List all patients         5. Delete a patient")
        print("   3. Search patients           6. Visit history")
        print("   0. Back")
        choice = input_int("  Choose : ", 0, 6)
        if choice == 0:
            return
        try:
            if choice == 1:
                register_patient()
            elif choice == 2:
                show_patients(patient_service.get_all())
            elif choice == 3:
                show_patients(patient_service.search(input_text("  Search term : ")))
            elif choice == 4:
                update_patient()
            elif choice == 5:
                delete_patient()
            elif choice == 6:
                show_history()
        except (PatientError, DatabaseError, ValueError) as e:
            warn(str(e))
        pause()


def show_patients(patients):
    if not patients:
        warn("No patient found.")
        return
    print(f"\n  {'ID':<6} {'Name':<22} {'S':<3} {'Age':<4} {'Phone':<12} {'Blood':<5} Allergies")
    print("  " + "-" * 72)
    for p in patients:
        print("  " + p.display_info())
    print(f"  ({len(patients)} patient(s))")


def register_patient():
    print("\n  New patient")
    patient = patient_service.add_patient(
        input_text("  Full name        : "),
        input_gender(),
        input_int("  Age              : ", 0, 120),
        input_phone("  Phone            : "),
        input_text("  Address          : ", allow_empty=True),
        input_text("  Blood type       : ", allow_empty=True),
        input_text("  Allergies        : ", allow_empty=True),
    )
    ok(f"Registered {patient.name} as {patient.id}")
    auth_service.log_action(user["username"], f"Registered patient {patient.id}")


def update_patient():
    patient = patient_service.get_patient(input_text("  Patient ID : "))
    if patient is None:
        warn("No patient with that ID.")
        return
    print("  " + patient.display_info())
    print("  Leave a field empty to keep it as it is.")
    patient_service.update_patient(
        patient.id,
        name=input_text("  Name       : ", allow_empty=True),
        age=input_int("  Age        : ", 0, 120, allow_empty=True),
        phone=input_phone("  Phone      : ", allow_empty=True),
        address=input_text("  Address    : ", allow_empty=True),
        blood_type=input_text("  Blood type : ", allow_empty=True),
        allergies=input_text("  Allergies  : ", allow_empty=True),
    )
    ok("Patient updated.")
    auth_service.log_action(user["username"], f"Updated patient {patient.id}")


def delete_patient():
    if not allowed("admin"):
        warn("Only an admin can delete a patient.")
        return
    patient_id = input_text("  Patient ID : ")
    patient = patient_service.get_patient(patient_id)
    if patient is None:
        warn("No patient with that ID.")
        return
    print("  " + patient.display_info())
    if confirm("  Delete this patient? (y/n): "):
        patient_service.delete_patient(patient_id)
        ok("Patient deleted.")
        auth_service.log_action(user["username"], f"Deleted patient {patient_id}")


def show_history():
    patient_id = input_text("  Patient ID : ")
    patient = patient_service.get_patient(patient_id)
    if patient is None:
        warn("No patient with that ID.")
        return
    print(f"\n  Visit history for {patient.name} ({patient.id})")
    table(patient_service.visit_history(patient_id),
          ["date", "time", "doctor_name", "diagnosis", "status", "grand_total", "payment_status"],
          ["Date", "Time", "Doctor", "Diagnosis", "Status", "Total", "Paid"],
          [11, 6, 18, 22, 10, 8, 8])


# ------------------------------------------------------------------ doctors
def doctor_menu():
    while True:
        section("DOCTOR & DEPARTMENT MANAGEMENT")
        print("   1. List doctors              5. Add a department")
        print("   2. Search doctors            6. List departments")
        print("   3. Register a doctor         7. Manage shifts")
        print("   4. Activate / deactivate     0. Back")
        choice = input_int("  Choose : ", 0, 7)
        if choice == 0:
            return
        try:
            if choice == 1:
                show_doctors(doctor_service.get_all(active_only=False))
            elif choice == 2:
                show_doctors(doctor_service.search(input_text("  Search term : ")))
            elif choice == 3:
                register_doctor()
            elif choice == 4:
                toggle_doctor()
            elif choice == 5:
                add_department()
            elif choice == 6:
                show_departments()
            elif choice == 7:
                shift_menu()
        except (DoctorError, DatabaseError, ValueError) as e:
            warn(str(e))
        pause()


def show_doctors(doctors):
    if not doctors:
        warn("No doctor found.")
        return
    print(f"\n  {'ID':<6} {'Name':<22} {'S':<3} {'Age':<4} {'Phone':<12} {'Specialization':<16} Fee")
    print("  " + "-" * 82)
    for d in doctors:
        print("  " + d.display_info())
    print(f"  ({len(doctors)} doctor(s))")


def show_departments():
    departments = doctor_service.get_departments()
    if not departments:
        warn("No department yet.")
        return
    print(f"\n  {'ID':<6} {'Name':<20} {'Location':<16} Phone")
    print("  " + "-" * 56)
    for d in departments:
        print("  " + d.display_info())


def add_department():
    if not allowed("admin"):
        warn("Only an admin can add a department.")
        return
    dept = doctor_service.add_department(
        input_text("  Department name : "),
        input_text("  Location        : ", allow_empty=True),
        input_phone("  Phone           : ", allow_empty=True),
    )
    ok(f"Added {dept.name} as {dept.id}")


def register_doctor():
    if not allowed("admin"):
        warn("Only an admin can register a doctor.")
        return
    show_departments()
    doctor = doctor_service.add_doctor(
        input_text("  Department ID    : "),
        input_text("  Full name        : "),
        input_gender(),
        input_int("  Age              : ", 20, 90),
        input_phone("  Phone            : "),
        input_text("  Specialization   : "),
        input_float("  Consultation fee : "),
    )
    ok(f"Registered Dr. {doctor.name} as {doctor.id}")
    auth_service.log_action(user["username"], f"Registered doctor {doctor.id}")
    if confirm("  Add shifts for this doctor now? (y/n): "):
        add_shift(doctor.id)


def toggle_doctor():
    if not allowed("admin"):
        warn("Only an admin can change a doctor's status.")
        return
    doctor = doctor_service.get_doctor(input_text("  Doctor ID : "))
    if doctor is None:
        warn("No doctor with that ID.")
        return
    new_state = not doctor.is_active
    doctor_service.set_active(doctor.id, new_state)
    ok(f"Dr. {doctor.name} is now {'active' if new_state else 'inactive'}.")
    auth_service.log_action(user["username"],
                            f"{'Activated' if new_state else 'Deactivated'} doctor {doctor.id}")


def shift_menu():
    doctor = doctor_service.get_doctor(input_text("  Doctor ID : "))
    if doctor is None:
        warn("No doctor with that ID.")
        return
    while True:
        print(f"\n  Shifts for Dr. {doctor.name}")
        shifts = doctor_service.get_schedules(doctor.id)
        if shifts:
            for s in shifts:
                print("   " + s.display_info())
        else:
            warn("No shift defined yet, so this doctor cannot be booked.")
        print("\n   1. Add a shift   2. Delete a shift   0. Back")
        choice = input_int("  Choose : ", 0, 2)
        if choice == 0:
            return
        try:
            if choice == 1:
                add_shift(doctor.id)
            elif choice == 2:
                doctor_service.delete_schedule(input_text("  Shift ID : "))
                ok("Shift removed.")
        except DoctorError as e:
            warn(str(e))


def add_shift(doctor_id):
    shift = doctor_service.add_schedule(
        doctor_id,
        input_day(),
        input_time("  Start time (HH:MM): "),
        input_time("  End time   (HH:MM): "),
        input_int("  Slot minutes      : ", 5, 120),
    )
    ok(f"Shift {shift.id} added.")


# ------------------------------------------------------------- appointments
def appointment_menu():
    while True:
        section("APPOINTMENT MANAGEMENT")
        print("   1. Show free slots           5. Mark as No-show")
        print("   2. Book an appointment       6. Complete a visit")
        print("   3. Cancel an appointment     7. Print a receipt")
        print("   4. View appointments         0. Back")
        choice = input_int("  Choose : ", 0, 7)
        if choice == 0:
            return
        try:
            if choice == 1:
                show_slots()
            elif choice == 2:
                book_appointment()
            elif choice == 3:
                change_status(appointment_service.cancel, "cancelled")
            elif choice == 4:
                view_appointments()
            elif choice == 5:
                change_status(appointment_service.mark_no_show, "marked No-show")
            elif choice == 6:
                complete_visit()
            elif choice == 7:
                receipt.print_and_save(input_text("  Appointment ID : "))
        except (AppointmentError, DoctorError, BillingError, DatabaseError, ValueError) as e:
            warn(str(e))
        pause()


def show_slots(doctor_id=None, date_str=None):
    doctor_id = doctor_id or input_text("  Doctor ID : ")
    date_str = date_str or input_date("  Date (YYYY-MM-DD) : ", no_past=True)
    slots = doctor_service.free_slots(doctor_id, date_str)
    if not slots:
        warn("Every slot that day is already taken.")
        return None, None, []
    print(f"\n  Free slots on {date_str}:")
    for i in range(0, len(slots), 8):
        print("   " + "  ".join(slots[i:i + 8]))
    return doctor_id, date_str, slots


def book_appointment():
    patient_id = input_text("  Patient ID : ")
    if patient_service.get_patient(patient_id) is None:
        warn("No patient with that ID. Register the patient first.")
        return
    show_departments()
    dept_id = input_text("  Department ID : ")
    doctors = doctor_service.by_department(dept_id)
    if not doctors:
        warn("No active doctor in that department.")
        return
    show_doctors(doctors)
    doctor_id, date_str, slots = show_slots()
    if not slots:
        return
    time_str = input_choice("  Choose a slot (HH:MM) : ", slots)
    reason = input_text("  Reason : ", allow_empty=True)
    appt = appointment_service.book(patient_id, doctor_id, date_str, time_str,
                                    user["username"], reason)
    ok(f"Booked {appt.id} on {appt.date} at {appt.time}. Fee ${appt.fee:.2f}")
    auth_service.log_action(user["username"], f"Booked {appt.id}")


def change_status(action, word):
    appt_id = input_text("  Appointment ID : ")
    appt = appointment_service.get(appt_id)
    if appt is None:
        warn("No appointment with that ID.")
        return
    print("  " + appt.display_info())
    if confirm(f"  Confirm this is {word}? (y/n): "):
        action(appt_id)
        ok(f"Appointment {word}.")
        auth_service.log_action(user["username"], f"{word.title()} {appt_id}")


def view_appointments():
    print("\n   1. By date   2. By doctor   3. By patient   4. Today")
    choice = input_int("  Choose : ", 1, 4)
    if choice == 1:
        rows = appointment_service.by_date(input_date("  Date (YYYY-MM-DD) : "))
    elif choice == 2:
        rows = appointment_service.by_doctor(input_text("  Doctor ID : "))
    elif choice == 3:
        rows = appointment_service.by_patient(input_text("  Patient ID : "))
    else:
        rows = appointment_service.by_date(today())
    table(rows,
          ["appointment_id", "date", "time", "patient_name", "doctor_name", "status", "grand_total"],
          ["ID", "Date", "Time", "Patient", "Doctor", "Status", "Total"],
          [6, 11, 6, 20, 20, 10, 8])


def complete_visit():
    appt_id = input_text("  Appointment ID : ")
    appt = appointment_service.get(appt_id)
    if appt is None:
        warn("No appointment with that ID.")
        return
    print("\n  Medical record")
    record_id = appointment_service.add_record(
        appt_id,
        input_text("  Symptoms       : "),
        input_text("  Diagnosis      : "),
        input_text("  Treatment      : "),
        input_text("  Notes          : ", allow_empty=True),
        input_date("  Follow-up date : ", allow_empty=True),
    )
    appt, invoice = appointment_service.complete(appt_id)
    ok(f"Visit completed. Record {record_id}, invoice {invoice.id}.")

    while confirm("  Add a prescription? (y/n): "):
        show_medicines()
        try:
            billing_service.prescribe(
                record_id,
                input_text("  Medicine ID : "),
                input_int("  Quantity    : ", 1),
                input_text("  Dosage      : ", allow_empty=True),
            )
            ok("Prescription added and stock updated.")
        except BillingError as e:
            warn(str(e))

    invoice = billing_service.get_invoice_for(appt_id)
    print(f"\n  Total to pay: ${invoice.grand_total:.2f}")
    if confirm("  Take payment now? (y/n): "):
        method = input_choice("  Method (Cash/Card/ABA) : ", ["Cash", "Card", "ABA"])
        billing_service.mark_paid(invoice.id, method)
        ok("Invoice marked as paid.")
    receipt.print_and_save(appt_id)
    auth_service.log_action(user["username"], f"Completed {appt_id}")


# ------------------------------------------------------------------ billing
def billing_menu():
    while True:
        section("BILLING & PHARMACY")
        print("   1. Unpaid invoices           4. Restock a medicine")
        print("   2. Mark an invoice paid      5. Low stock and expiry")
        print("   3. Medicine list             6. Add a medicine")
        print("   0. Back")
        choice = input_int("  Choose : ", 0, 6)
        if choice == 0:
            return
        try:
            if choice == 1:
                table(billing_service.unpaid_invoices(),
                      ["id", "date", "patient_name", "doctor_name", "grand_total"],
                      ["Invoice", "Date", "Patient", "Doctor", "Amount"],
                      [8, 11, 20, 20, 9])
            elif choice == 2:
                invoice = billing_service.mark_paid(
                    input_text("  Invoice ID : "),
                    input_choice("  Method (Cash/Card/ABA) : ", ["Cash", "Card", "ABA"]))
                ok(f"{invoice.id} paid, ${invoice.grand_total:.2f}")
            elif choice == 3:
                show_medicines()
            elif choice == 4:
                med = billing_service.restock(input_text("  Medicine ID : "),
                                              input_int("  Quantity to add : ", 1))
                ok(f"{med.name} now has {med.stock_qty} {med.unit}(s).")
            elif choice == 5:
                show_stock_warnings()
            elif choice == 6:
                add_medicine()
        except (BillingError, DatabaseError, ValueError) as e:
            warn(str(e))
        pause()


def show_medicines():
    medicines = billing_service.get_medicines()
    if not medicines:
        warn("No medicine in stock.")
        return
    print(f"\n  {'ID':<6} {'Name':<22} {'Price':>7} {'Stock':>5} {'Unit':<8} Expiry")
    print("  " + "-" * 62)
    for m in medicines:
        print("  " + m.display_info())


def show_stock_warnings():
    low = billing_service.low_stock()
    soon = billing_service.expiring_soon()
    print("\n  Low stock:")
    if low:
        for m in low:
            print(f"   {m.name:<24} {m.stock_qty} left (reorder at {m.reorder_at})")
    else:
        print("   nothing to reorder")
    print("\n  Expiring within 30 days:")
    if soon:
        for m in soon:
            print(f"   {m.name:<24} expires {m.expiry_date}")
    else:
        print("   nothing expiring soon")


def add_medicine():
    if not allowed("admin"):
        warn("Only an admin can add a medicine.")
        return
    med = billing_service.add_medicine(
        input_text("  Name         : "),
        input_text("  Category     : ", allow_empty=True),
        input_text("  Unit         : "),
        input_float("  Unit price   : "),
        input_int("  Stock        : ", 0),
        input_int("  Reorder at   : ", 0),
        input_date("  Expiry date  : ", allow_empty=True),
    )
    ok(f"Added {med.name} as {med.id}")


# ------------------------------------------------------------------ reports
def report_menu():
    while True:
        section("REPORTS")
        print("   1. Today's appointment sheet   5. Busiest weekdays")
        print("   2. Income by doctor            6. Appointment status summary")
        print("   3. Income by department        7. Audit log")
        print("   4. Busiest doctors             0. Back")
        choice = input_int("  Choose : ", 0, 7)
        if choice == 0:
            return
        try:
            rows, name = run_report(choice)
            if rows and confirm("  Export this to CSV? (y/n): "):
                path = report_service.export_csv(rows, name)
                ok(f"Saved to {path}")
        except (DatabaseError, ValueError) as e:
            warn(str(e))
        pause()


def run_report(choice):
    if choice == 1:
        rows = report_service.daily_sheet()
        table(rows, ["time", "appointment_id", "patient_name", "doctor_name", "status", "grand_total"],
              ["Time", "ID", "Patient", "Doctor", "Status", "Total"], [6, 6, 20, 20, 10, 8])
        return rows, "daily_sheet"
    if choice in (2, 3):
        if not allowed("admin"):
            warn("Only an admin can see income reports.")
            return None, ""
        start = input_date("  From (YYYY-MM-DD) : ")
        end = input_date("  To   (YYYY-MM-DD) : ")
        if choice == 2:
            rows = report_service.income_by_doctor(start, end)
            table(rows, ["doctor_name", "department", "visits", "income"],
                  ["Doctor", "Department", "Visits", "Income"], [22, 20, 7, 10])
            return rows, "income_by_doctor"
        rows = report_service.income_by_department(start, end)
        table(rows, ["department", "visits", "income"],
              ["Department", "Visits", "Income"], [22, 7, 10])
        return rows, "income_by_department"
    if choice == 4:
        rows = report_service.busiest_doctors()
        table(rows, ["doctor_name", "specialization", "visits"],
              ["Doctor", "Specialization", "Visits"], [22, 20, 7])
        return rows, "busiest_doctors"
    if choice == 5:
        rows = report_service.busiest_weekdays()
        table(rows, ["weekday", "visits"], ["Weekday", "Visits"], [12, 7])
        return rows, "busiest_weekdays"
    if choice == 6:
        rows = report_service.status_summary()
        table(rows, ["status", "total"], ["Status", "Count"], [12, 7])
        return rows, "status_summary"
    if not allowed("admin"):
        warn("Only an admin can read the audit log.")
        return None, ""
    rows = auth_service.read_audit_log()
    table(rows, ["timestamp", "username", "action"],
          ["When", "User", "Action"], [17, 14, 34])
    return rows, "audit_log"


# -------------------------------------------------------------------- users
def user_menu():
    while True:
        section("USER ACCOUNTS")
        print("   1. List users   2. Create a user   3. Deactivate   4. Reset password   0. Back")
        choice = input_int("  Choose : ", 0, 4)
        if choice == 0:
            return
        try:
            if choice == 1:
                table(auth_service.list_users(),
                      ["username", "role", "linked_doctor_id", "is_active"],
                      ["Username", "Role", "Doctor", "Active"], [16, 14, 8, 7])
            elif choice == 2:
                role = input_choice("  Role (admin/receptionist/doctor) : ",
                                    list(auth_service.ROLES))
                linked = input_text("  Doctor ID : ") if role == "doctor" else None
                auth_service.create_user(input_text("  Username : "),
                                         input_text("  Password : "), role, linked)
                ok("User created.")
            elif choice == 3:
                auth_service.deactivate_user(input_text("  Username : "))
                ok("User deactivated.")
            elif choice == 4:
                auth_service.reset_password(input_text("  Username : "),
                                            input_text("  New password : "))
                ok("Password reset.")
        except (ValueError, DatabaseError) as e:
            warn(str(e))
        pause()


# ------------------------------------------------------------- doctor's view
def my_appointments():
    section("MY APPOINTMENTS")
    doctor_id = user["linked_doctor_id"]
    rows = appointment_service.by_doctor(doctor_id, only_upcoming=True)
    table(rows, ["appointment_id", "date", "time", "patient_name", "status"],
          ["ID", "Date", "Time", "Patient", "Status"], [6, 11, 6, 22, 10])
    pause()


# --------------------------------------------------------------- main menus
def dashboard():
    summary = report_service.patient_summary()
    print(f"\n  Patients {summary['patients']}   Doctors {summary['doctors']}   "
          f"Appointments {summary['appointments']}   Paid income ${summary['income']:.2f}")
    warnings = billing_service.low_stock()
    if warnings and allowed("admin"):
        warn(f"{len(warnings)} medicine(s) at or below the reorder level.")


def main_menu():
    options = {}
    section(f"MAIN MENU   -   {user['username']} ({user['role']})")
    if allowed("admin", "receptionist"):
        print("   1. Patients")
        print("   2. Doctors & departments")
        print("   3. Appointments")
        print("   4. Billing & pharmacy")
        print("   5. Reports")
        options = {1: patient_menu, 2: doctor_menu, 3: appointment_menu,
                   4: billing_menu, 5: report_menu}
    if allowed("admin"):
        print("   6. User accounts")
        options[6] = user_menu
    if allowed("doctor"):
        print("   1. My appointments")
        print("   2. Complete a visit")
        print("   3. Patient visit history")
        options = {1: my_appointments, 2: doctor_complete, 3: show_history_safe}
    print("   0. Log out and exit")
    return options


def doctor_complete():
    section("COMPLETE A VISIT")
    try:
        complete_visit()
    except (AppointmentError, BillingError, ValueError) as e:
        warn(str(e))
    pause()


def show_history_safe():
    section("PATIENT VISIT HISTORY")
    try:
        show_history()
    except (PatientError, ValueError) as e:
        warn(str(e))
    pause()


def main():
    global user
    if "--sqlite" in sys.argv:
        db.set_backend("sqlite")
    elif "--mysql" in sys.argv:
        db.set_backend("mysql")

    try:
        db.init_db()
        auth_service.ensure_default_admin()
    except DatabaseError as e:
        print(f"Cannot start: {e}")
        sys.exit(1)

    user = login_screen()
    if user is None:
        print("\n  Too many failed attempts. Goodbye.")
        sys.exit(0)

    auth_service.log_action(user["username"], "Logged in")
    dashboard()

    while True:
        options = main_menu()
        choice = input_int("  Choose : ", 0, max(options))
        if choice == 0:
            auth_service.log_action(user["username"], "Logged out")
            print("\n  Goodbye.\n")
            break
        action = options.get(choice)
        if action is None:
            warn("That option is not available for your role.")
            continue
        action()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Stopped by the user.\n")
    except EOFError:
        print("\n\n  Input ended. Goodbye.\n")
    except Exception as e:                       # last safety net
        print(f"\n  Unexpected error: {e}\n")
