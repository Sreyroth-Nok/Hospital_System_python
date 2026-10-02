"""
receipt.py - Build a printable receipt and save a copy as a text file.
Owner: Person 1
"""

import os

from services import billing_service
from utils import database as db
from config import DATA_DIR
from utils.validator import now_stamp

WIDTH = 46
RECEIPT_DIR = os.path.join(DATA_DIR, "receipts")


def build(appointment_id):
    """Return the receipt for one appointment as a block of text."""
    row = db.query_one(
        """SELECT a.id, a.date, a.time, p.name AS patient_name, p.id AS patient_id,
                  p.age, d.name AS doctor_name, d.specialization, dp.name AS department
           FROM appointments a
           JOIN patients p ON p.id = a.patient_id
           JOIN doctors d ON d.id = a.doctor_id
           JOIN departments dp ON dp.id = d.department_id
           WHERE a.id = ?""",
        (appointment_id.upper(),),
    )
    if row is None:
        raise ValueError(f"No appointment with ID {appointment_id}.")
    invoice = billing_service.get_invoice_for(appointment_id)
    if invoice is None:
        raise ValueError("This visit has no invoice yet.")

    line = "=" * WIDTH
    thin = "-" * WIDTH
    out = [
        line,
        "CITY GENERAL HOSPITAL".center(WIDTH),
        "Official Receipt".center(WIDTH),
        line,
        f"Receipt   : {invoice.id}",
        f"Visit     : {row['id']}   {row['date']} {row['time']}",
        f"Patient   : {row['patient_name']} ({row['patient_id']}, age {row['age']})",
        f"Doctor    : Dr. {row['doctor_name']} - {row['specialization']}",
        f"Department: {row['department']}",
        thin,
    ]

    out.append(f"{'Consultation fee':<32}{invoice.consult_fee:>14.2f}")
    medicines = billing_service.prescriptions_for_appointment(appointment_id)
    for med in medicines:
        label = f"  {med['name']} x{med['quantity']}"
        out.append(f"{label:<32}{med['line_total']:>14.2f}")
    if medicines:
        out.append(f"{'Medicines subtotal':<32}{invoice.medicine_total:>14.2f}")
    out.append(f"{'Service charge':<32}{invoice.service_fee:>14.2f}")
    if invoice.discount:
        out.append(f"{'Discount (age)':<32}{-invoice.discount:>14.2f}")
    out.append(thin)
    out.append(f"{'TOTAL':<32}{invoice.grand_total:>14.2f}")
    out.append(f"{'Status':<32}{invoice.payment_status:>14}")
    if invoice.payment_method:
        out.append(f"{'Paid by':<32}{invoice.payment_method:>14}")
    out.append(line)
    out.append(f"Printed {now_stamp()}")
    out.append("Thank you and get well soon.".center(WIDTH))
    out.append(line)
    return "\n".join(out)


def save(appointment_id):
    """Write the receipt to data/receipts/<appointment id>.txt and return the path."""
    text = build(appointment_id)
    os.makedirs(RECEIPT_DIR, exist_ok=True)
    path = os.path.join(RECEIPT_DIR, f"{appointment_id.upper()}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return path


def print_and_save(appointment_id):
    text = build(appointment_id)
    print("\n" + text)
    path = save(appointment_id)
    print(f"\nSaved to {path}")
    return path
