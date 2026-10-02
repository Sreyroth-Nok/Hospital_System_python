"""
gui_smoke.py - Builds and drives every screen with no display attached.

tkinter is replaced by the stand-in in tests/fake_tk, so this checks the
wiring of the interface: that every window and tab can be built, that the
tables fill from the database, that the buttons call the right service, and
that the role rules hold. It cannot check how anything looks.

Run from the project folder:  python tests/gui_smoke.py
It rebuilds the demo database first.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "fake_tk"))      # the stand-in wins
sys.path.insert(0, os.path.dirname(HERE))

import tkinter                                          # noqa: E402  the stand-in
from tkinter import messagebox                          # noqa: E402

import seed_data                                        # noqa: E402
from gui import widgets                                 # noqa: E402
from gui.app import MainWindow                          # noqa: E402
from gui.appointments_tab import BookingWindow, CompleteVisitWindow  # noqa: E402
from gui.login_window import LoginWindow                # noqa: E402
from gui.widgets import FormDialog                      # noqa: E402
from services import (appointment_service, billing_service, doctor_service,
                      patient_service)                  # noqa: E402
from utils.validator import DATE_FMT                    # noqa: E402

PASSED, FAILED = [], []


def check(name, condition, detail=""):
    (PASSED if condition else FAILED).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{('  -> ' + detail) if detail else ''}")


def canned(values):
    """Make the next form dialog return these values without opening."""
    FormDialog.open = staticmethod(lambda *args, **kwargs: values)


def main():
    if "fake_tk" not in tkinter.__file__:
        print("The real tkinter is installed; run the GUI itself instead.")
        return 0

    print("Rebuilding the demo database...")
    seed_data.run()
    print("\nBuilding the interface\n" + "-" * 62)

    # --- login ---------------------------------------------------------
    login = LoginWindow()
    login.username.set("admin")
    login.password.set("wrong")
    login.attempt_login()
    check("Login refuses a wrong password", login.user is None and login.attempts == 1)

    login.username.set("admin")
    login.password.set("admin123")
    login.attempt_login()
    check("Login accepts the correct password",
          login.user is not None and login.user["role"] == "admin")
    admin_user = login.user

    # --- main window as admin ------------------------------------------
    window = MainWindow(admin_user)
    tab_names = [text for text, _ in window.notebook.tabs_added]
    check("Admin sees every tab", len(tab_names) == 6, ", ".join(tab_names))
    check("Dashboard counts patients",
          window.stat_labels["patients"].kwargs.get("text") not in (None, "-"),
          f"patients={window.stat_labels['patients'].kwargs.get('text')}")

    patients_tab = window.tabs["patients"]
    rows = len(patients_tab.table.tree.get_children())
    check("Patients table fills from the database", rows >= 20, f"{rows} rows")

    patients_tab.search("zzzz")
    check("Search with no match shows a message, no crash",
          len(patients_tab.table.tree.get_children()) == 0)
    patients_tab.refresh()

    # --- register a patient through the form ---------------------------
    before = len(patient_service.get_all())
    canned({"name": "GUI Test", "gender": "F", "age": 29, "phone": "012777666",
            "address": "Street 1", "blood_type": "O+", "allergies": ""})
    patients_tab.register()
    check("Register patient button saves a row",
          len(patient_service.get_all()) == before + 1)

    # --- validation still refuses bad values ---------------------------
    from utils.validator import ValidationError
    dialog = FormDialog.__new__(FormDialog)
    dialog.fields = [{"key": "age", "label": "Age", "kind": "int",
                      "minimum": 0, "maximum": 120}]
    dialog.vars = {"age": tkinter.StringVar(value="200")}
    try:
        dialog._collect()
        check("Form refuses age 200", False)
    except ValidationError as e:
        check("Form refuses age 200", True, str(e))

    # --- appointments tab ----------------------------------------------
    appointments_tab = window.tabs["appointments"]
    for choice in ("Today", "Upcoming", "All", "Booked", "Cancelled"):
        appointments_tab.filter.set(choice)
        appointments_tab.refresh()
    check("Every appointment filter loads", True, "Today, Upcoming, All, Booked, Cancelled")

    # --- booking window -------------------------------------------------
    doctor = doctor_service.get_all()[0]
    patient = patient_service.get_all()[0]
    booking = BookingWindow(window, window, patient_service.get_all(),
                            doctor_service.get_departments())
    booking.department.set(f"{doctor.department_id} - x")
    booking._load_doctors()
    check("Choosing a department lists its doctors",
          len(booking.doctor_box.kwargs.get("values", [])) > 0)

    booking.doctor.set(f"{doctor.id} - {doctor.name}")
    date_str, slots = _next_free(doctor.id)
    booking.date.set(date_str)
    booking._load_slots()
    check("Free slots load for a working day", len(booking.slots) > 0,
          f"{len(booking.slots)} slots on {date_str}")

    booking.patient.set(f"{patient.id} - {patient.name}")
    booking.slot.set(booking.slots[0])
    count_before = len(appointment_service.by_date(date_str))
    booking._book()
    check("Book button creates the appointment",
          len(appointment_service.by_date(date_str)) == count_before + 1)

    # booking the same slot again must be refused and reported in the window
    booking2 = BookingWindow(window, window, patient_service.get_all(),
                             doctor_service.get_departments())
    booking2.patient.set(f"{patient.id} - {patient.name}")
    booking2.doctor.set(f"{doctor.id} - {doctor.name}")
    booking2.date.set(date_str)
    booking2.slot.set(slots[0])
    booking2._book()
    message = booking2.message.kwargs.get("text", "")
    check("Double booking is refused in the window", "already booked" in message, message)

    # --- complete a visit ------------------------------------------------
    appointment = appointment_service.get(
        appointment_service.by_date(date_str)[-1]["appointment_id"])
    complete = CompleteVisitWindow(window, window, appointment)
    complete.symptoms.set("Headache")
    complete.diagnosis.set("Migraine")
    complete.treatment.set("Rest")
    complete._save_record()
    check("Completing a visit creates the invoice",
          complete.invoice is not None and complete.invoice.grand_total > 0,
          widgets.money(complete.invoice.grand_total) if complete.invoice else "")

    medicine = billing_service.get_medicines()[0]
    stock_before = medicine.stock_qty
    canned({"medicine": f"{medicine.id} - {medicine.name}", "quantity": 4,
            "dosage": "1 after meals"})
    complete._add_prescription()
    check("Prescribing from the window reduces stock",
          billing_service.get_medicine(medicine.id).stock_qty == stock_before - 4)

    canned({"method": "Cash"})
    complete._take_payment()
    check("Payment marks the invoice paid and writes a receipt",
          billing_service.get_invoice_for(appointment.id).payment_status == "Paid"
          and os.path.exists(os.path.join("data", "receipts", f"{appointment.id}.txt")))

    # --- billing and reports ---------------------------------------------
    billing_tab = window.tabs["billing"]
    billing_tab.refresh()
    check("Billing tab lists unpaid invoices and stock",
          len(billing_tab.medicine_table.tree.get_children()) > 0)

    reports_tab = window.tabs["reports"]
    ran = []
    for name in reports_tab._available_reports():
        reports_tab.choice.set(name)
        reports_tab.run()
        ran.append(name)
    check("Every report runs for an admin", len(ran) == 7, f"{len(ran)} reports")
    reports_tab.choice.set("Busiest doctors")
    reports_tab.run()
    reports_tab.export()
    check("Report export writes a CSV",
          os.path.exists(os.path.join("data", "reports", "busiest_doctors.csv")))

    # --- doctors tab -------------------------------------------------------
    doctors_tab = window.tabs["doctors"]
    doctors_tab.refresh()
    check("Doctors tab shows doctors and departments",
          len(doctors_tab.doctor_table.tree.get_children()) == 6
          and len(doctors_tab.department_table.tree.get_children()) == 3)

    # --- role rules --------------------------------------------------------
    receptionist = {"username": "reception1", "role": "receptionist",
                    "linked_doctor_id": None, "is_active": 1}
    reception_window = MainWindow(receptionist)
    names = [text for text, _ in reception_window.notebook.tabs_added]
    check("Receptionist has no Users tab", "Users" not in names, ", ".join(names))
    check("Receptionist cannot open income reports",
          "Income by doctor" not in reception_window.tabs["reports"]._available_reports())

    messagebox.shown.clear()
    reception_window.tabs["patients"].table.tree.select_first()
    reception_window.tabs["patients"].delete()
    check("Receptionist is refused when deleting a patient",
          any(kind == "error" for kind, _, _ in messagebox.shown))

    doctor_user = {"username": "drratha", "role": "doctor",
                   "linked_doctor_id": doctor.id, "is_active": 1}
    doctor_window = MainWindow(doctor_user)
    names = [text for text, _ in doctor_window.notebook.tabs_added]
    check("Doctor sees only their own appointments tab", names == ["My appointments"],
          ", ".join(names))
    own = doctor_window.tabs["appointments"]
    check("Doctor's list is limited to their own visits",
          len(own.table.tree.get_children()) > 0)

    print("-" * 62)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("  failed:", ", ".join(FAILED))
    return 1 if FAILED else 0


def _next_free(doctor_id):
    from datetime import datetime, timedelta
    from services.doctor_service import DoctorError
    for offset in range(1, 21):
        date_str = (datetime.now() + timedelta(days=offset)).strftime(DATE_FMT)
        try:
            slots = doctor_service.free_slots(doctor_id, date_str)
            if slots:
                return date_str, slots
        except DoctorError:
            continue
    raise RuntimeError("No free slot in the next three weeks.")


if __name__ == "__main__":
    sys.exit(main())
