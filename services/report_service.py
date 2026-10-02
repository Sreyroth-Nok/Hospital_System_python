"""
report_service.py - Every report the hospital reads, plus CSV export.
Owner: Person 4
"""

import csv
import os

from utils import database as db
from config import DATA_DIR
from utils.validator import today

REPORT_DIR = os.path.join(DATA_DIR, "reports")


def daily_sheet(date_str=None):
    """Every appointment on one date, earliest first."""
    return db.query(
        """SELECT time, appointment_id, patient_name, doctor_name, department,
                  status, grand_total, payment_status
           FROM v_appointment_full WHERE date = ? ORDER BY time""",
        (date_str or today(),),
    )


def income_by_doctor(start, end):
    return db.query(
        """SELECT d.id, d.name AS doctor_name, dp.name AS department,
                  COUNT(i.id) AS visits, SUM(i.grand_total) AS income
           FROM invoices i
           JOIN appointments a ON a.id = i.appointment_id
           JOIN doctors d ON d.id = a.doctor_id
           JOIN departments dp ON dp.id = d.department_id
           WHERE i.payment_status = 'Paid' AND a.date BETWEEN ? AND ?
           GROUP BY d.id ORDER BY income DESC""",
        (start, end),
    )


def income_by_department(start, end):
    return db.query(
        """SELECT dp.name AS department, COUNT(i.id) AS visits,
                  SUM(i.grand_total) AS income
           FROM invoices i
           JOIN appointments a ON a.id = i.appointment_id
           JOIN doctors d ON d.id = a.doctor_id
           JOIN departments dp ON dp.id = d.department_id
           WHERE i.payment_status = 'Paid' AND a.date BETWEEN ? AND ?
           GROUP BY dp.id ORDER BY income DESC""",
        (start, end),
    )


def busiest_doctors(limit=5):
    return db.query(
        """SELECT d.name AS doctor_name, d.specialization, COUNT(a.id) AS visits
           FROM appointments a JOIN doctors d ON d.id = a.doctor_id
           WHERE a.status = 'Completed'
           GROUP BY d.id ORDER BY visits DESC LIMIT ?""",
        (limit,),
    )


def busiest_weekdays():
    """Which weekday is busiest. The weekday expression differs between
    MySQL and SQLite, so it comes from the database layer."""
    expr = db.weekday_expression("date")
    return db.query(
        f"""SELECT {expr} AS weekday, COUNT(*) AS visits
           FROM appointments WHERE status IN ('Booked', 'Completed')
           GROUP BY weekday ORDER BY visits DESC"""
    )


def status_summary():
    return db.query(
        "SELECT status, COUNT(*) AS total FROM appointments GROUP BY status ORDER BY total DESC"
    )


def patient_summary():
    return db.query_one(
        """SELECT (SELECT COUNT(*) FROM patients)     AS patients,
                  (SELECT COUNT(*) FROM doctors WHERE is_active = 1) AS doctors,
                  (SELECT COUNT(*) FROM appointments) AS appointments,
                  (SELECT COALESCE(SUM(grand_total), 0) FROM invoices
                    WHERE payment_status = 'Paid')    AS income"""
    )


def export_csv(rows, filename):
    """Write any list of rows to data/reports/<filename>.csv."""
    if not rows:
        raise ValueError("There is nothing to export.")
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, filename if filename.endswith(".csv") else filename + ".csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow([row[k] for k in row.keys()])
    return path
