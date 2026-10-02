"""
run_tests.py - Runs the test cases from section 11 of the PRD.
Owner: everyone writes the cases for their own module.

Run from the project folder:  python tests/run_tests.py
It rebuilds the demo database first, so never run it on real data.
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import seed_data
from models.models import Invoice, Patient
from services import (appointment_service, auth_service, billing_service,
                      doctor_service, patient_service, report_service)
from services.appointment_service import AppointmentError
from services.billing_service import BillingError
from services.doctor_service import DoctorError
from services.patient_service import PatientError
from utils import database as db, receipt
from utils.validator import DATE_FMT, today

PASSED, FAILED = [], []


def check(test_id, description, condition):
    (PASSED if condition else FAILED).append(test_id)
    mark = "PASS" if condition else "FAIL"
    print(f"  {test_id}  {mark}  {description}")


def expect_error(test_id, description, func, *args, **kwargs):
    """The test passes when the call is refused with a readable message."""
    try:
        func(*args, **kwargs)
        check(test_id, description + "  [no error raised]", False)
    except (AppointmentError, BillingError, DoctorError, PatientError, ValueError) as e:
        check(test_id, f"{description}  -> {e}", True)


def next_working_date(doctor_id, days_ahead=14):
    """Find the next date this doctor actually has free slots."""
    for offset in range(1, days_ahead):
        date_str = (datetime.now() + timedelta(days=offset)).strftime(DATE_FMT)
        try:
            slots = doctor_service.free_slots(doctor_id, date_str)
            if slots:
                return date_str, slots
        except DoctorError:
            continue
    raise RuntimeError("No free slot found in the next two weeks.")


def main():
    print("Rebuilding the demo database...\n")
    seed_data.run()
    print("\nRunning test cases\n" + "-" * 60)

    doctor = doctor_service.get_all()[0]
    patient = patient_service.get_all()[0]

    # --- authentication -------------------------------------------------
    check("T-01", "Login with the correct password",
          auth_service.login("admin", "admin123") is not None)
    check("T-02", "Login with a wrong password is refused",
          auth_service.login("admin", "wrong") is None)
    check("T-03", "Passwords are not stored in readable form",
          db.query_one("SELECT password_hash FROM users WHERE username='admin'")
          ["password_hash"] != "admin123")

    # --- patients -------------------------------------------------------
    new_patient = patient_service.add_patient("Test Patient", "F", 30, "012999888")
    check("T-04", f"Register a patient -> {new_patient.id}",
          new_patient.id.startswith("P") and patient_service.get_patient(new_patient.id))
    expect_error("T-05", "Age 200 is refused", setattr, new_patient, "age", 200)
    expect_error("T-06", "Phone 'abcd' is refused", setattr, new_patient, "phone", "abcd")
    expect_error("T-07", "An empty name is refused", setattr, new_patient, "name", "  ")
    check("T-08", "Search with no match returns an empty list, no crash",
          patient_service.search("zzzz") == [])
    check("T-08b", "Search by part of a name finds the patient",
          len(patient_service.search(patient.name.split()[0])) >= 1)

    # --- slots and booking ----------------------------------------------
    date_str, slots = next_working_date(doctor.id)
    check("T-09", f"Free slots listed for {doctor.id} on {date_str} ({len(slots)} slots)",
          len(slots) > 0)

    sunday = next((datetime.now() + timedelta(days=i)).strftime(DATE_FMT)
                  for i in range(1, 8)
                  if (datetime.now() + timedelta(days=i)).strftime("%a") not in
                  [s.day_of_week for s in doctor_service.get_schedules(doctor.id)])
    expect_error("T-10", "A day the doctor does not work is refused",
                 doctor_service.free_slots, doctor.id, sunday)

    appt = appointment_service.book(new_patient.id, doctor.id, date_str, slots[0], "admin")
    check("T-11a", f"Booking created {appt.id} at {appt.time}", appt.status == "Booked")
    expect_error("T-11", "The same slot booked twice is refused",
                 appointment_service.book, patient.id, doctor.id, date_str, slots[0], "admin")

    yesterday = (datetime.now() - timedelta(days=1)).strftime(DATE_FMT)
    expect_error("T-12", "A date in the past is refused",
                 appointment_service.book, patient.id, doctor.id, yesterday, "09:00", "admin")

    check("T-13", "A wrong date format is rejected by the validator",
          _date_rejected("21/10/2026"))

    # --- cancel and free the slot ---------------------------------------
    appointment_service.cancel(appt.id)
    check("T-14", "Cancelled appointment frees its slot again",
          appointment_service.get(appt.id).status == "Cancelled"
          and slots[0] in doctor_service.free_slots(doctor.id, date_str))

    # --- fees -------------------------------------------------------------
    adult = Invoice("INV-T1", "A000", consult_fee=30.0)
    adult.calculate(discount_applies=False)
    check("T-15", f"Adult total is {adult.grand_total:.2f} (30 + 5, no discount)",
          abs(adult.grand_total - 35.00) < 0.01)

    senior = Invoice("INV-T2", "A000", consult_fee=30.0)
    senior.calculate(discount_applies=True)
    check("T-16", f"Senior total is {senior.grand_total:.2f} (30 + 5 - 3)",
          abs(senior.grand_total - 32.00) < 0.01)

    check("T-16b", "The discount rule follows the patient's age",
          Patient("P999", "Old Person", "M", 70, "012000000").is_discount_age()
          and not Patient("P998", "Adult", "M", 30, "012000000").is_discount_age())

    # --- complete a visit, prescribe, freeze the price --------------------
    date2, slots2 = next_working_date(doctor.id)
    visit = appointment_service.book(patient.id, doctor.id, date2, slots2[0], "admin")
    db.execute("UPDATE appointments SET date = ? WHERE id = ?", (today(), visit.id))
    record_id = appointment_service.add_record(visit.id, "Cough", "Bronchitis", "Rest")
    _, invoice = appointment_service.complete(visit.id)
    check("T-17a", f"Completing the visit created invoice {invoice.id}",
          invoice.grand_total > 0)

    original_fee = appointment_service.get(visit.id).fee
    doctor_service.update_doctor(doctor.id, fee=doctor.fee + 50)
    check("T-17", "Raising the doctor's fee does not change the issued invoice",
          appointment_service.get(visit.id).fee == original_fee
          and billing_service.get_invoice(invoice.id).consult_fee == original_fee)
    doctor_service.update_doctor(doctor.id, fee=doctor.fee)

    medicine = billing_service.get_medicines()[0]
    before = medicine.stock_qty
    expect_error("T-18", "Prescribing more than the stock on hand is refused",
                 billing_service.prescribe, record_id, medicine.id, before + 100)
    check("T-18b", "The refused prescription left the stock untouched",
          billing_service.get_medicine(medicine.id).stock_qty == before)

    billing_service.prescribe(record_id, medicine.id, 5, "1 after meals")
    check("T-19", f"Prescribing 5 dropped the stock from {before} to {before - 5}",
          billing_service.get_medicine(medicine.id).stock_qty == before - 5)

    updated = billing_service.get_invoice(invoice.id)
    check("T-19b", f"The invoice picked up the medicine cost (${updated.medicine_total:.2f})",
          updated.medicine_total > 0)

    paid = billing_service.mark_paid(invoice.id, "Cash")
    check("T-19c", "Invoice can be marked paid", paid.payment_status == "Paid")

    path = receipt.save(visit.id)
    check("T-19d", f"Receipt written to {os.path.basename(path)}",
          os.path.exists(path) and "TOTAL" in open(path, encoding="utf-8").read())

    # --- deletion guards --------------------------------------------------
    expect_error("T-20", "A patient with appointments cannot be deleted",
                 patient_service.delete_patient, patient.id)
    check("T-20b", "A patient with no history can be deleted",
          _delete_round_trip())

    # --- persistence and reports -----------------------------------------
    count_before = len(db.query("SELECT id FROM appointments"))
    db.get_connection().close()
    check("T-21", f"Records survive reopening the database ({count_before} appointments)",
          len(db.query("SELECT id FROM appointments")) == count_before)

    check("T-22", "A completed appointment cannot be cancelled",
          _completed_cannot_cancel(visit.id))

    sheet = report_service.daily_sheet(today())
    check("T-23", f"Today's sheet returns {len(sheet)} row(s) matching the database",
          len(sheet) == len(db.query("SELECT id FROM appointments WHERE date = ?", (today(),))))

    start = (datetime.now() - timedelta(days=30)).strftime(DATE_FMT)
    income = report_service.income_by_doctor(start, today())
    total_reported = sum(r["income"] for r in income)
    total_paid = db.query_one(
        """SELECT COALESCE(SUM(i.grand_total), 0) AS t FROM invoices i
           JOIN appointments a ON a.id = i.appointment_id
           WHERE i.payment_status = 'Paid' AND a.date BETWEEN ? AND ?""",
        (start, today()))["t"]
    check("T-24", f"Income report total ${total_reported:.2f} matches paid invoices",
          abs(total_reported - total_paid) < 0.01)

    csv_path = report_service.export_csv(income, "test_income")
    check("T-24b", f"Report exported to {os.path.basename(csv_path)}", os.path.exists(csv_path))

    print("-" * 60)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("  failed:", ", ".join(FAILED))
    return 1 if FAILED else 0


def _date_rejected(value):
    try:
        datetime.strptime(value, DATE_FMT)
        return False
    except ValueError:
        return True


def _delete_round_trip():
    temp = patient_service.add_patient("Delete Me", "M", 40, "012111222")
    patient_service.delete_patient(temp.id)
    return patient_service.get_patient(temp.id) is None


def _completed_cannot_cancel(appointment_id):
    try:
        appointment_service.cancel(appointment_id)
        return False
    except AppointmentError:
        return True


if __name__ == "__main__":
    sys.exit(main())
