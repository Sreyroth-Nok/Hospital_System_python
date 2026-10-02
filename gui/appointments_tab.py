"""
appointments_tab.py - Booking, cancelling and completing visits.
Owner: Person 4
"""

import tkinter as tk
from tkinter import ttk

from gui import widgets
from gui.widgets import DataTable, FormDialog, Toolbar
from services import (appointment_service, auth_service, billing_service,
                      doctor_service, patient_service)
from services.appointment_service import AppointmentError
from services.billing_service import BillingError
from services.doctor_service import DoctorError
from utils import database as db, receipt
from utils.validator import today

COLUMNS = [
    ("appointment_id", "ID", 70), ("date", "Date", 100), ("time", "Time", 70),
    ("patient_name", "Patient", 160), ("doctor_name", "Doctor", 160),
    ("department", "Department", 130), ("status", "Status", 90),
    ("grand_total", "Total", 90), ("payment_status", "Payment", 90),
]


class AppointmentsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Card.TFrame", padding=14)
        self.app = app

        ttk.Label(self, text="Appointments", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self, text="The system offers only the slots a doctor actually has "
                             "free, so a double booking cannot be made.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(fill="x")
        Toolbar(bar, [
            ("Book appointment", self.book, "primary"),
            ("Complete visit", self.complete, None),
            ("Cancel", self.cancel, "danger"),
            ("No-show", self.no_show, None),
            ("Receipt", self.show_receipt, None),
        ]).pack(side="left")

        filters = ttk.Frame(bar, style="Card.TFrame")
        filters.pack(side="right", pady=8)
        ttk.Label(filters, text="Show", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        self.filter = tk.StringVar(value="Today")
        chooser = ttk.Combobox(filters, textvariable=self.filter, state="readonly",
                               width=14,
                               values=["Today", "Upcoming", "All", "Booked",
                                       "Completed", "Cancelled", "No-show"])
        chooser.pack(side="left")
        chooser.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        ttk.Button(filters, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))

        self.table = DataTable(self, COLUMNS, on_double_click=self.show_receipt)
        self.table.pack(fill="both", expand=True, pady=(10, 6))
        self.count = ttk.Label(self, text="", style="Muted.TLabel")
        self.count.pack(anchor="w")
        self.refresh()

    # ------------------------------------------------------------ loading
    def refresh(self):
        choice = self.filter.get()
        try:
            if choice == "Today":
                rows = appointment_service.by_date(today())
            elif choice == "Upcoming":
                rows = db.query("SELECT * FROM v_appointment_full WHERE date >= ? "
                                "ORDER BY date, time", (today(),))
            elif choice == "All":
                rows = db.query("SELECT * FROM v_appointment_full "
                                "ORDER BY date DESC, time")
            else:
                rows = appointment_service.by_status(choice)
        except db.DatabaseError as e:
            widgets.error(str(e))
            return
        total = self.table.set_rows(rows, formatter=lambda r: dict(
            r, grand_total=widgets.money(r["grand_total"]) if r["grand_total"] else "-",
            payment_status=r["payment_status"] or "-"))
        self.count.configure(text=f"{total} appointment(s) · {choice.lower()}")

    def _selected_id(self):
        appointment_id = self.table.selected_value("appointment_id")
        if appointment_id is None:
            widgets.error("Choose an appointment from the list first.", "Nothing selected")
        return appointment_id

    # ------------------------------------------------------------- booking
    def book(self):
        try:
            patients = patient_service.get_all()
            departments = doctor_service.get_departments()
        except db.DatabaseError as e:
            widgets.error(str(e))
            return
        if not patients:
            widgets.error("Register a patient first.", "No patients")
            return
        BookingWindow(self, self.app, patients, departments)
        self.refresh()
        self.app.refresh_dashboard()

    # ------------------------------------------------------------- changes
    def cancel(self):
        appointment_id = self._selected_id()
        if appointment_id is None:
            return
        if not widgets.ask(f"Cancel appointment {appointment_id}?\n"
                           "The slot becomes free again straight away."):
            return
        self._apply(appointment_service.cancel, appointment_id, "Cancelled")

    def no_show(self):
        appointment_id = self._selected_id()
        if appointment_id is None:
            return
        if not widgets.ask(f"Mark {appointment_id} as a no-show?"):
            return
        self._apply(appointment_service.mark_no_show, appointment_id, "No-show")

    def _apply(self, action, appointment_id, word):
        try:
            action(appointment_id)
        except (AppointmentError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"{word} {appointment_id}")
        self.refresh()
        self.app.refresh_dashboard()

    def complete(self):
        appointment_id = self._selected_id()
        if appointment_id is None:
            return
        appointment = appointment_service.get(appointment_id)
        if appointment is None:
            widgets.error("That appointment no longer exists.")
            return
        if appointment.status != "Booked":
            widgets.error(f"Only a booked visit can be completed "
                          f"(this one is {appointment.status}).")
            return
        CompleteVisitWindow(self, self.app, appointment)
        self.refresh()
        self.app.refresh_dashboard()

    def show_receipt(self):
        appointment_id = self.table.selected_value("appointment_id")
        if appointment_id is None:
            widgets.error("Choose an appointment from the list first.", "Nothing selected")
            return
        try:
            text = receipt.build(appointment_id)
        except (ValueError, db.DatabaseError) as e:
            widgets.error(str(e), "No receipt yet")
            return

        def save():
            path = receipt.save(appointment_id)
            widgets.info(f"Saved to\n{path}")

        widgets.TextWindow(self, f"Receipt {appointment_id}", text, on_save=save)


class BookingWindow(tk.Toplevel):
    """Patient, department, doctor, date, then a slot chosen from a real list."""

    def __init__(self, master, app, patients, departments):
        super().__init__(master)
        self.app = app
        self.patients = patients
        self.departments = departments
        self.slots = []

        self.title("Book an appointment")
        self.configure(background=widgets.SURFACE)
        self.transient(master)
        self.resizable(False, False)

        frame = ttk.Frame(self, style="Card.TFrame", padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Book an appointment", style="Heading.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self.patient = tk.StringVar()
        self.department = tk.StringVar()
        self.doctor = tk.StringVar()
        self.date = tk.StringVar(value=today())
        self.slot = tk.StringVar()
        self.reason = tk.StringVar()

        self._row(frame, 1, "Patient", ttk.Combobox(
            frame, textvariable=self.patient, state="readonly", width=34,
            values=[f"{p.id} - {p.name} (age {p.age})" for p in patients]))

        department_box = ttk.Combobox(
            frame, textvariable=self.department, state="readonly", width=34,
            values=[f"{d.id} - {d.name}" for d in departments])
        department_box.bind("<<ComboboxSelected>>", lambda event: self._load_doctors())
        self._row(frame, 2, "Department", department_box)

        self.doctor_box = ttk.Combobox(frame, textvariable=self.doctor,
                                       state="readonly", width=34, values=[])
        self.doctor_box.bind("<<ComboboxSelected>>", lambda event: self._load_slots())
        self._row(frame, 3, "Doctor", self.doctor_box)

        date_row = ttk.Frame(frame, style="Card.TFrame")
        ttk.Entry(date_row, textvariable=self.date, width=14).pack(side="left")
        ttk.Button(date_row, text="Find free slots",
                   command=self._load_slots).pack(side="left", padx=(8, 0))
        self._row(frame, 4, "Date (YYYY-MM-DD)", date_row)

        self.slot_box = ttk.Combobox(frame, textvariable=self.slot,
                                     state="readonly", width=34, values=[])
        self._row(frame, 5, "Free slot", self.slot_box)
        self._row(frame, 6, "Reason", ttk.Entry(frame, textvariable=self.reason, width=36))

        self.message = ttk.Label(frame, text="Choose a department to begin.",
                                 style="Muted.TLabel", wraplength=360)
        self.message.grid(row=7, column=0, columnspan=2, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.grid(row=8, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Book", command=self._book,
                   style="Primary.TButton").pack(side="right")

        self.grab_set()
        master.wait_window(self)

    @staticmethod
    def _row(frame, index, label, widget):
        ttk.Label(frame, text=label, style="Card.TLabel").grid(
            row=index, column=0, sticky="w", pady=6, padx=(0, 14))
        widget.grid(row=index, column=1, sticky="ew", pady=6)

    def _load_doctors(self):
        self.doctor.set("")
        self.slot_box.configure(values=[])
        self.slot.set("")
        department_id = self.department.get().split(" - ")[0]
        doctors = doctor_service.by_department(department_id)
        self.doctor_box.configure(
            values=[f"{d.id} - {d.name} ({widgets.money(d.fee)})" for d in doctors])
        self.message.configure(
            text="No active doctor in that department." if not doctors
            else "Choose a doctor, then a date.")

    def _load_slots(self):
        self.slot.set("")
        doctor_id = self.doctor.get().split(" - ")[0]
        if not doctor_id:
            self.message.configure(text="Choose a doctor first.")
            return
        try:
            self.slots = doctor_service.free_slots(doctor_id, self.date.get().strip())
        except (DoctorError, ValueError, db.DatabaseError) as e:
            self.slots = []
            self.slot_box.configure(values=[])
            self.message.configure(text=str(e))
            return
        self.slot_box.configure(values=self.slots)
        if self.slots:
            self.slot.set(self.slots[0])
            self.message.configure(text=f"{len(self.slots)} free slot(s) on that date.")
        else:
            self.message.configure(text="Every slot that day is taken. Try another date.")

    def _book(self):
        patient_id = self.patient.get().split(" - ")[0]
        doctor_id = self.doctor.get().split(" - ")[0]
        if not patient_id or not doctor_id or not self.slot.get():
            self.message.configure(text="Choose a patient, a doctor and a free slot.")
            return
        try:
            appointment = appointment_service.book(
                patient_id, doctor_id, self.date.get().strip(), self.slot.get(),
                self.app.username, self.reason.get().strip())
        except (AppointmentError, db.DatabaseError) as e:
            # Refresh the slots first, then show why it was refused, or the
            # refreshed list would overwrite the message.
            self._load_slots()
            self.message.configure(text=str(e))
            return
        auth_service.log_action(self.app.username, f"Booked {appointment.id}")
        widgets.info(f"Booked {appointment.id} on {appointment.date} at "
                     f"{appointment.time}.\nFee {widgets.money(appointment.fee)}.")
        self.destroy()


class CompleteVisitWindow(tk.Toplevel):
    """Medical record, prescriptions, invoice and payment in one screen."""

    def __init__(self, master, app, appointment):
        super().__init__(master)
        self.app = app
        self.appointment = appointment
        self.record_id = None
        self.invoice = None

        self.title(f"Complete visit {appointment.id}")
        self.configure(background=widgets.SURFACE)
        self.transient(master)

        frame = ttk.Frame(self, style="Card.TFrame", padding=18)
        frame.pack(fill="both", expand=True)

        patient = patient_service.get_patient(appointment.patient_id)
        doctor = doctor_service.get_doctor(appointment.doctor_id)
        ttk.Label(frame, text=f"Visit {appointment.id}", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text=f"{patient.name} ({patient.id}, age {patient.age}) with "
                              f"Dr. {doctor.name} on {appointment.date} at {appointment.time}",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(frame, style="Card.TFrame")
        form.pack(fill="x")
        self.symptoms = tk.StringVar()
        self.diagnosis = tk.StringVar()
        self.treatment = tk.StringVar()
        self.follow_up = tk.StringVar()
        for index, (label, variable) in enumerate([
                ("Symptoms", self.symptoms), ("Diagnosis", self.diagnosis),
                ("Treatment", self.treatment), ("Follow-up date (optional)", self.follow_up)]):
            ttk.Label(form, text=label, style="Card.TLabel").grid(
                row=index, column=0, sticky="w", pady=5, padx=(0, 14))
            ttk.Entry(form, textvariable=variable, width=46).grid(
                row=index, column=1, sticky="ew", pady=5)
        form.grid_columnconfigure(1, weight=1)

        self.save_button = ttk.Button(frame, text="Save record and create invoice",
                                      command=self._save_record, style="Primary.TButton")
        self.save_button.pack(anchor="w", pady=(12, 10))

        self.prescription_frame = ttk.Frame(frame, style="Card.TFrame")
        self.prescription_frame.pack(fill="both", expand=True)
        ttk.Label(self.prescription_frame, text="Prescriptions",
                  style="Heading.TLabel").pack(anchor="w")
        Toolbar(self.prescription_frame, [
            ("Add medicine", self._add_prescription, None),
        ]).pack(anchor="w")
        self.prescription_table = DataTable(self.prescription_frame, [
            ("name", "Medicine", 190), ("dosage", "Dosage", 150),
            ("quantity", "Qty", 60), ("unit_price", "Price", 80),
            ("line_total", "Line total", 100)], height=5)
        self.prescription_table.pack(fill="both", expand=True, pady=(6, 10))

        self.total_label = ttk.Label(frame, text="", style="Stat.TLabel")
        self.total_label.pack(anchor="w")

        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        self.pay_button = ttk.Button(buttons, text="Take payment and print receipt",
                                     command=self._take_payment, style="Primary.TButton")
        self.pay_button.pack(side="left")
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")

        self._set_stage(record_saved=False)
        self.grab_set()
        master.wait_window(self)

    def _set_stage(self, record_saved):
        state = "normal" if record_saved else "disabled"
        for child in self.prescription_frame.winfo_children():
            try:
                child.configure(state=state)
            except Exception:
                pass
        self.pay_button.configure(state=state)

    def _save_record(self):
        if not self.symptoms.get().strip() or not self.diagnosis.get().strip():
            widgets.error("Symptoms and diagnosis are both needed.")
            return
        try:
            self.record_id = appointment_service.add_record(
                self.appointment.id, self.symptoms.get().strip(),
                self.diagnosis.get().strip(), self.treatment.get().strip(),
                "", self.follow_up.get().strip())
            _, self.invoice = appointment_service.complete(self.appointment.id)
        except (AppointmentError, BillingError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        auth_service.log_action(self.app.username, f"Completed {self.appointment.id}")
        self.save_button.configure(state="disabled")
        self._set_stage(record_saved=True)
        self._refresh_total()

    def _refresh_total(self):
        self.invoice = billing_service.get_invoice_for(self.appointment.id)
        self.prescription_table.set_rows(
            billing_service.prescriptions_for(self.record_id) if self.record_id else [],
            formatter=lambda r: dict(r, unit_price=widgets.money(r["unit_price"]),
                                     line_total=widgets.money(r["line_total"])))
        if self.invoice:
            self.total_label.configure(
                text=f"Total {widgets.money(self.invoice.grand_total)}"
                     f"   ({self.invoice.payment_status})")

    def _add_prescription(self):
        if not self.record_id:
            widgets.error("Save the medical record first.")
            return
        medicines = [m for m in billing_service.get_medicines() if m.stock_qty > 0]
        if not medicines:
            widgets.error("No medicine is in stock.", "Pharmacy empty")
            return
        values = FormDialog.open(self, "Add a prescription", [
            {"key": "medicine", "label": "Medicine", "kind": "choice",
             "options": [f"{m.id} - {m.name} ({m.stock_qty} {m.unit} left)"
                         for m in medicines]},
            {"key": "quantity", "label": "Quantity", "kind": "int", "minimum": 1},
            {"key": "dosage", "label": "Dosage", "kind": "text", "required": False,
             "default": "1 after meals"},
        ], submit_label="Prescribe")
        if not values:
            return
        try:
            billing_service.prescribe(self.record_id,
                                      values["medicine"].split(" - ")[0],
                                      values["quantity"], values["dosage"])
        except (BillingError, db.DatabaseError) as e:
            widgets.error(str(e))
            return
        self._refresh_total()

    def _take_payment(self):
        if self.invoice is None:
            widgets.error("Save the medical record first.")
            return
        if self.invoice.payment_status != "Paid":
            values = FormDialog.open(self, "Take payment", [
                {"key": "method", "label": "Payment method", "kind": "choice",
                 "options": ["Cash", "Card", "ABA"], "default": "Cash"},
            ], submit_label="Mark as paid",
                intro=f"Amount due {widgets.money(self.invoice.grand_total)}")
            if not values:
                return
            try:
                billing_service.mark_paid(self.invoice.id, values["method"])
            except (BillingError, db.DatabaseError) as e:
                widgets.error(str(e))
                return
        self._refresh_total()
        path = receipt.save(self.appointment.id)
        widgets.TextWindow(self, f"Receipt {self.appointment.id}",
                           receipt.build(self.appointment.id))
        widgets.info(f"Receipt saved to\n{path}")
