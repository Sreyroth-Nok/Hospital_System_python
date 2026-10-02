"""
billing_tab.py - Unpaid invoices, payments and the medicine stock.
Owner: Person 4
"""

from tkinter import ttk

from gui import widgets
from gui.widgets import DataTable, FormDialog, Toolbar
from services import auth_service, billing_service
from services.billing_service import BillingError
from utils import database as db

INVOICE_COLUMNS = [
    ("id", "Invoice", 90), ("date", "Visit date", 100),
    ("patient_name", "Patient", 170), ("doctor_name", "Doctor", 170),
    ("grand_total", "Amount", 100),
]
MEDICINE_COLUMNS = [
    ("id", "ID", 70), ("name", "Medicine", 190), ("category", "Category", 130),
    ("unit_price", "Price", 80), ("stock_qty", "Stock", 70), ("unit", "Unit", 80),
    ("expiry_date", "Expires", 100), ("flag", "Warning", 110),
]


class BillingTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Card.TFrame", padding=14)
        self.app = app

        ttk.Label(self, text="Billing & pharmacy", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="Prescribing takes medicine out of stock automatically.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        inner = ttk.Notebook(self)
        inner.pack(fill="both", expand=True)
        self.invoice_page = ttk.Frame(inner, style="Card.TFrame", padding=10)
        self.medicine_page = ttk.Frame(inner, style="Card.TFrame", padding=10)
        inner.add(self.invoice_page, text="Unpaid invoices")
        inner.add(self.medicine_page, text="Medicines")

        Toolbar(self.invoice_page, [
            ("Mark as paid", self.mark_paid, "primary"),
            ("Refresh", self.refresh, None),
        ]).pack(fill="x")
        self.invoice_table = DataTable(self.invoice_page, INVOICE_COLUMNS)
        self.invoice_table.pack(fill="both", expand=True, pady=(10, 6))
        self.invoice_total = ttk.Label(self.invoice_page, text="", style="Muted.TLabel")
        self.invoice_total.pack(anchor="w")

        Toolbar(self.medicine_page, [
            ("Add medicine", self.add_medicine, "primary"),
            ("Restock", self.restock, None),
            ("Refresh", self.refresh, None),
        ]).pack(fill="x")
        self.medicine_table = DataTable(self.medicine_page, MEDICINE_COLUMNS)
        self.medicine_table.pack(fill="both", expand=True, pady=(10, 6))
        self.stock_note = ttk.Label(self.medicine_page, text="", style="Muted.TLabel")
        self.stock_note.pack(anchor="w")

        self.refresh()

    # ------------------------------------------------------------ loading
    def refresh(self):
        try:
            invoices = billing_service.unpaid_invoices()
            medicines = billing_service.get_medicines()
            expiring = {m.id for m in billing_service.expiring_soon()}
        except db.DatabaseError as e:
            widgets.error(str(e))
            return

        self.invoice_table.set_rows(invoices, formatter=lambda r: dict(
            r, grand_total=widgets.money(r["grand_total"])))
        outstanding = sum(float(r["grand_total"]) for r in invoices)
        self.invoice_total.configure(
            text=f"{len(invoices)} unpaid invoice(s), {widgets.money(outstanding)} outstanding")

        self.medicine_table.set_rows(medicines, formatter=lambda m: {
            "id": m.id, "name": m.name, "category": m.category or "-",
            "unit_price": widgets.money(m.unit_price), "stock_qty": m.stock_qty,
            "unit": m.unit or "-", "expiry_date": m.expiry_date or "-",
            "flag": self._flag(m, expiring),
        })
        low = [m for m in medicines if m.is_low_stock()]
        self.stock_note.configure(
            text=f"{len(low)} medicine(s) at or below the reorder level, "
                 f"{len(expiring)} expiring within 30 days")

    @staticmethod
    def _flag(medicine, expiring):
        notes = []
        if medicine.is_low_stock():
            notes.append("low stock")
        if medicine.id in expiring:
            notes.append("expiring")
        return ", ".join(notes) or "-"

    # ------------------------------------------------------------ actions
    def mark_paid(self):
        invoice_id = self.invoice_table.selected_value("id")
        if invoice_id is None:
            widgets.error("Choose an invoice from the list first.", "Nothing selected")
            return
        values = FormDialog.open(self, "Take payment", [
            {"key": "method", "label": "Payment method", "kind": "choice",
             "options": ["Cash", "Card", "ABA"], "default": "Cash"},
        ], submit_label="Mark as paid")
        if not values:
            return
        try:
            invoice = billing_service.mark_paid(invoice_id, values["method"])
        except (BillingError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Paid invoice {invoice.id}")
        widgets.info(f"{invoice.id} marked as paid, {widgets.money(invoice.grand_total)}.")
        self.refresh()
        self.app.refresh_dashboard()

    def add_medicine(self):
        if self.app.role != "admin":
            widgets.error("Only an admin can add a medicine.", "Not allowed")
            return
        values = FormDialog.open(self, "Add a medicine", [
            {"key": "name", "label": "Name", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "text", "required": False},
            {"key": "unit", "label": "Unit (tablet, bottle...)", "kind": "text"},
            {"key": "unit_price", "label": "Unit price", "kind": "float"},
            {"key": "stock_qty", "label": "Stock on hand", "kind": "int", "minimum": 0},
            {"key": "reorder_at", "label": "Warn when stock reaches", "kind": "int",
             "minimum": 0, "default": 10},
            {"key": "expiry_date", "label": "Expiry date", "kind": "date",
             "required": False},
        ], submit_label="Add")
        if not values:
            return
        try:
            medicine = billing_service.add_medicine(**values)
        except (BillingError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        widgets.info(f"{medicine.name} added as {medicine.id}.")
        self.refresh()

    def restock(self):
        medicine_id = self.medicine_table.selected_value("id")
        if medicine_id is None:
            widgets.error("Choose a medicine from the list first.", "Nothing selected")
            return
        values = FormDialog.open(self, "Restock", [
            {"key": "quantity", "label": "Quantity to add", "kind": "int", "minimum": 1},
        ], submit_label="Add to stock")
        if not values:
            return
        try:
            medicine = billing_service.restock(medicine_id, values["quantity"])
        except (BillingError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Restocked {medicine.id}")
        widgets.info(f"{medicine.name} now has {medicine.stock_qty} {medicine.unit}(s).")
        self.refresh()
        self.app.refresh_dashboard()
