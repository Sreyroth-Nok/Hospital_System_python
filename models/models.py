"""
models.py - The objects the system works with.
Agreed by the whole group before any service was written.

Shows inheritance (Patient and Doctor extend Person), encapsulation
(private attributes reached through properties with validation) and
method overriding (display_info redefined in each subclass).
"""

from datetime import datetime


class Person:
    """Base class for everyone the hospital stores: patients and doctors."""

    def __init__(self, person_id, name, gender, age, phone):
        self._id = person_id
        self._name = name
        self._gender = gender
        self._age = age
        self._phone = phone

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not value or not value.strip():
            raise ValueError("Name cannot be empty.")
        self._name = value.strip()

    @property
    def gender(self):
        return self._gender

    @property
    def age(self):
        return self._age

    @age.setter
    def age(self, value):
        if not isinstance(value, int) or not 0 <= value <= 120:
            raise ValueError("Age must be a whole number between 0 and 120.")
        self._age = value

    @property
    def phone(self):
        return self._phone

    @phone.setter
    def phone(self, value):
        if not str(value).isdigit() or not 8 <= len(str(value)) <= 15:
            raise ValueError("Phone must be 8 to 15 digits.")
        self._phone = str(value)

    def display_info(self):
        """One line describing this person. Subclasses extend this."""
        return f"{self._id:<6} {self._name:<22} {self._gender:<3} {self._age:<4} {self._phone}"


class Patient(Person):
    """Someone who visits the hospital."""

    def __init__(self, person_id, name, gender, age, phone, address="",
                 blood_type="", allergies="", created_at=None):
        super().__init__(person_id, name, gender, age, phone)
        self.address = address
        self.blood_type = blood_type
        self.allergies = allergies
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d")

    def is_discount_age(self):
        """True for children under 5 and seniors over 60."""
        return self._age < 5 or self._age > 60

    def display_info(self):                       # method overriding
        base = super().display_info()
        return f"{base} {self.blood_type:<5} {self.allergies or '-'}"

    def to_tuple(self):
        return (self._id, self._name, self._gender, self._age, self._phone,
                self.address, self.blood_type, self.allergies, self.created_at)

    @staticmethod
    def from_row(row):
        return Patient(row["id"], row["name"], row["gender"], row["age"],
                       row["phone"], row["address"], row["blood_type"],
                       row["allergies"], row["created_at"])


class Doctor(Person):
    """A doctor employed by a department."""

    def __init__(self, person_id, department_id, name, gender, age, phone,
                 specialization="", fee=0.0, is_active=1):
        super().__init__(person_id, name, gender, age, phone)
        self.department_id = department_id
        self.specialization = specialization
        self.fee = fee
        self.is_active = is_active

    @property
    def fee(self):
        return self._fee

    @fee.setter
    def fee(self, value):
        value = float(value)
        if value < 0:
            raise ValueError("Consultation fee cannot be negative.")
        self._fee = value

    def display_info(self):                       # method overriding
        base = super().display_info()
        status = "" if self.is_active else "  [inactive]"
        return f"{base} {self.specialization:<16} ${self._fee:>7.2f}{status}"

    def to_tuple(self):
        return (self._id, self.department_id, self._name, self._gender, self._age,
                self._phone, self.specialization, self._fee, self.is_active)

    @staticmethod
    def from_row(row):
        return Doctor(row["id"], row["department_id"], row["name"], row["gender"],
                      row["age"], row["phone"], row["specialization"], row["fee"],
                      row["is_active"])


class Department:
    """A section of the hospital that doctors belong to."""

    def __init__(self, dept_id, name, location="", phone=""):
        self.id = dept_id
        self.name = name
        self.location = location
        self.phone = phone

    def display_info(self):
        return f"{self.id:<6} {self.name:<20} {self.location:<16} {self.phone}"

    def to_tuple(self):
        return (self.id, self.name, self.location, self.phone)


class Schedule:
    """One weekly shift for one doctor."""

    def __init__(self, schedule_id, doctor_id, day_of_week, start_time,
                 end_time, slot_minutes=30):
        self.id = schedule_id
        self.doctor_id = doctor_id
        self.day_of_week = day_of_week
        self.start_time = start_time
        self.end_time = end_time
        self.slot_minutes = slot_minutes

    def display_info(self):
        return (f"{self.id:<6} {self.day_of_week:<5} {self.start_time} - "
                f"{self.end_time}  every {self.slot_minutes} min")

    def to_tuple(self):
        return (self.id, self.doctor_id, self.day_of_week, self.start_time,
                self.end_time, self.slot_minutes)


class Appointment:
    """One booking between a patient and a doctor."""

    BOOKED, COMPLETED, CANCELLED, NO_SHOW = "Booked", "Completed", "Cancelled", "No-show"

    def __init__(self, appt_id, patient_id, doctor_id, created_by, date, time,
                 reason="", status=BOOKED, fee=0.0, created_at=None):
        self.id = appt_id
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.created_by = created_by
        self.date = date
        self.time = time
        self.reason = reason
        self.status = status
        self.fee = fee
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M")

    def display_info(self):
        return (f"{self.id:<6} {self.date} {self.time}  {self.patient_id:<6} "
                f"{self.doctor_id:<6} {self.status:<10} ${self.fee:>7.2f}")

    def to_tuple(self):
        return (self.id, self.patient_id, self.doctor_id, self.created_by,
                self.date, self.time, self.reason, self.status, self.fee,
                self.created_at)

    @staticmethod
    def from_row(row):
        return Appointment(row["id"], row["patient_id"], row["doctor_id"],
                           row["created_by"], row["date"], row["time"],
                           row["reason"], row["status"], row["fee"],
                           row["created_at"])


class Invoice:
    """The bill for one completed appointment."""

    SERVICE_FEE = 5.0
    DISCOUNT_RATE = 0.10

    def __init__(self, invoice_id, appointment_id, consult_fee=0.0,
                 medicine_total=0.0, service_fee=SERVICE_FEE, discount=0.0,
                 grand_total=0.0, payment_status="Unpaid", payment_method=None,
                 paid_at=None):
        self.id = invoice_id
        self.appointment_id = appointment_id
        self.consult_fee = consult_fee
        self.medicine_total = medicine_total
        self.service_fee = service_fee
        self.discount = discount
        self.grand_total = grand_total
        self.payment_status = payment_status
        self.payment_method = payment_method
        self.paid_at = paid_at

    def calculate(self, discount_applies):
        """Total = consultation fee + medicines + service charge - discount."""
        self.discount = self.consult_fee * Invoice.DISCOUNT_RATE if discount_applies else 0.0
        self.grand_total = (self.consult_fee + self.medicine_total
                            + self.service_fee - self.discount)
        return self.grand_total

    def display_info(self):
        return (f"{self.id:<8} {self.appointment_id:<6} ${self.grand_total:>8.2f}  "
                f"{self.payment_status}")

    def to_tuple(self):
        return (self.id, self.appointment_id, self.consult_fee, self.medicine_total,
                self.service_fee, self.discount, self.grand_total,
                self.payment_status, self.payment_method, self.paid_at)

    @staticmethod
    def from_row(row):
        return Invoice(row["id"], row["appointment_id"], row["consult_fee"],
                       row["medicine_total"], row["service_fee"], row["discount"],
                       row["grand_total"], row["payment_status"],
                       row["payment_method"], row["paid_at"])


class Medicine:
    """One item in the pharmacy stock."""

    def __init__(self, med_id, name, category="", unit="", unit_price=0.0,
                 stock_qty=0, reorder_at=10, expiry_date=""):
        self.id = med_id
        self.name = name
        self.category = category
        self.unit = unit
        self.unit_price = unit_price
        self.stock_qty = stock_qty
        self.reorder_at = reorder_at
        self.expiry_date = expiry_date

    def is_low_stock(self):
        return self.stock_qty <= self.reorder_at

    def display_info(self):
        flag = "  LOW" if self.is_low_stock() else ""
        return (f"{self.id:<6} {self.name:<22} ${self.unit_price:>6.2f} "
                f"{self.stock_qty:>5} {self.unit:<8} exp {self.expiry_date}{flag}")

    def to_tuple(self):
        return (self.id, self.name, self.category, self.unit, self.unit_price,
                self.stock_qty, self.reorder_at, self.expiry_date)
