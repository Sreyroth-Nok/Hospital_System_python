"""
billing_service.py - Invoices, payments, medicine stock and prescriptions.
Owner: Person 4
"""

from datetime import datetime, timedelta

from models.models import Invoice, Medicine
from utils import database as db
from utils.validator import DATE_FMT, now_stamp, today


class BillingError(Exception):
    """Raised when a billing or stock operation cannot be completed."""


# --------------------------------------------------------------- invoices
def create_invoice(appointment_id):
    """Build the invoice for a completed visit. Called by appointment_service."""
    appt = db.query_one(
        """SELECT a.id, a.fee, p.age
           FROM appointments a JOIN patients p ON p.id = a.patient_id
           WHERE a.id = ?""",
        (appointment_id.upper(),),
    )
    if appt is None:
        raise BillingError(f"No appointment with ID {appointment_id}.")
    existing = db.query_one("SELECT * FROM invoices WHERE appointment_id = ?", (appt["id"],))
    if existing:
        return Invoice.from_row(existing)

    invoice = Invoice(db.next_id("invoices", "INV"), appt["id"], appt["fee"], 0.0)
    discount_applies = appt["age"] < 5 or appt["age"] > 60
    invoice.calculate(discount_applies)
    db.execute("INSERT INTO invoices (id, appointment_id, consult_fee, medicine_total,"
               " service_fee, discount, grand_total, payment_status, payment_method,"
               " paid_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               invoice.to_tuple())
    return invoice


def get_invoice(invoice_id):
    row = db.query_one("SELECT * FROM invoices WHERE id = ?", (invoice_id.upper(),))
    return Invoice.from_row(row) if row else None


def get_invoice_for(appointment_id):
    row = db.query_one("SELECT * FROM invoices WHERE appointment_id = ?",
                       (appointment_id.upper(),))
    return Invoice.from_row(row) if row else None


def recalculate(invoice_id):
    """Rebuild the total after prescriptions were added."""
    invoice = get_invoice(invoice_id)
    if invoice is None:
        raise BillingError(f"No invoice with ID {invoice_id}.")
    row = db.query_one(
        """SELECT COALESCE(SUM(pr.line_total), 0) AS total, p.age
           FROM invoices i
           JOIN appointments a ON a.id = i.appointment_id
           JOIN patients p ON p.id = a.patient_id
           LEFT JOIN records r ON r.appointment_id = a.id
           LEFT JOIN prescriptions pr ON pr.record_id = r.id
           WHERE i.id = ?""",
        (invoice.id,),
    )
    invoice.medicine_total = row["total"]
    invoice.calculate(row["age"] < 5 or row["age"] > 60)
    db.execute(
        "UPDATE invoices SET medicine_total = ?, discount = ?, grand_total = ? WHERE id = ?",
        (invoice.medicine_total, invoice.discount, invoice.grand_total, invoice.id),
    )
    return invoice


def mark_paid(invoice_id, method="Cash"):
    invoice = get_invoice(invoice_id)
    if invoice is None:
        raise BillingError(f"No invoice with ID {invoice_id}.")
    if invoice.payment_status == "Paid":
        raise BillingError("This invoice is already paid.")
    db.execute(
        "UPDATE invoices SET payment_status = 'Paid', payment_method = ?, paid_at = ? WHERE id = ?",
        (method, now_stamp(), invoice.id),
    )
    return get_invoice(invoice_id)


def unpaid_invoices():
    return db.query(
        """SELECT i.id, i.grand_total, a.date, p.name AS patient_name, d.name AS doctor_name
           FROM invoices i
           JOIN appointments a ON a.id = i.appointment_id
           JOIN patients p ON p.id = a.patient_id
           JOIN doctors  d ON d.id = a.doctor_id
           WHERE i.payment_status = 'Unpaid'
           ORDER BY a.date"""
    )


# -------------------------------------------------------------- medicines
def add_medicine(name, category, unit, unit_price, stock_qty, reorder_at, expiry_date):
    med = Medicine(db.next_id("medicines", "M"), name, category, unit,
                   unit_price, stock_qty, reorder_at, expiry_date)
    try:
        db.execute("INSERT INTO medicines (id, name, category, unit, unit_price,"
                   " stock_qty, reorder_at, expiry_date)"
                   " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", med.to_tuple())
    except db.IntegrityError:
        raise BillingError(f"A medicine called '{name}' is already in stock.")
    return med


def get_medicine(med_id):
    row = db.query_one("SELECT * FROM medicines WHERE id = ?", (med_id.upper(),))
    return Medicine(row["id"], row["name"], row["category"], row["unit"],
                    row["unit_price"], row["stock_qty"], row["reorder_at"],
                    row["expiry_date"]) if row else None


def get_medicines():
    return [get_medicine(r["id"]) for r in db.query("SELECT id FROM medicines ORDER BY id")]


def restock(med_id, quantity):
    if get_medicine(med_id) is None:
        raise BillingError(f"No medicine with ID {med_id}.")
    db.execute("UPDATE medicines SET stock_qty = stock_qty + ? WHERE id = ?",
               (quantity, med_id.upper()))
    return get_medicine(med_id)


def low_stock():
    return [m for m in get_medicines() if m.is_low_stock()]


def expiring_soon(days=30):
    limit = (datetime.now() + timedelta(days=days)).strftime(DATE_FMT)
    rows = db.query(
        "SELECT id FROM medicines WHERE expiry_date <> '' AND expiry_date <= ? ORDER BY expiry_date",
        (limit,),
    )
    return [get_medicine(r["id"]) for r in rows]


# ----------------------------------------------------------- prescriptions
def prescribe(record_id, medicine_id, quantity, dosage=""):
    """Add one prescription line and take the medicine out of stock."""
    med = get_medicine(medicine_id)
    if med is None:
        raise BillingError(f"No medicine with ID {medicine_id}.")
    if quantity <= 0:
        raise BillingError("Quantity must be at least 1.")
    if quantity > med.stock_qty:
        raise BillingError(f"Only {med.stock_qty} {med.unit} of {med.name} left in stock.")
    if db.query_one("SELECT id FROM records WHERE id = ?", (record_id.upper(),)) is None:
        raise BillingError(f"No medical record with ID {record_id}.")

    line_total = round(med.unit_price * quantity, 2)
    pres_id = db.next_id("prescriptions", "PR")
    db.execute("INSERT INTO prescriptions (id, record_id, medicine_id, dosage,"
               " quantity, unit_price, line_total) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (pres_id, record_id.upper(), med.id, dosage, quantity,
                med.unit_price, line_total))
    db.execute("UPDATE medicines SET stock_qty = stock_qty - ? WHERE id = ?",
               (quantity, med.id))

    invoice = db.query_one(
        """SELECT i.id FROM invoices i
           JOIN records r ON r.appointment_id = i.appointment_id
           WHERE r.id = ?""",
        (record_id.upper(),),
    )
    if invoice:
        recalculate(invoice["id"])
    return pres_id


def prescriptions_for(record_id):
    return db.query(
        """SELECT pr.id, m.name, pr.dosage, pr.quantity, pr.unit_price, pr.line_total
           FROM prescriptions pr JOIN medicines m ON m.id = pr.medicine_id
           WHERE pr.record_id = ? ORDER BY pr.id""",
        (record_id.upper(),),
    )


def prescriptions_for_appointment(appointment_id):
    return db.query(
        """SELECT m.name, pr.dosage, pr.quantity, pr.unit_price, pr.line_total
           FROM prescriptions pr
           JOIN records r ON r.id = pr.record_id
           JOIN medicines m ON m.id = pr.medicine_id
           WHERE r.appointment_id = ? ORDER BY pr.id""",
        (appointment_id.upper(),),
    )
