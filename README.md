# Hospital Appointment & Patient Management System

Advanced Python major assignment · Group 1 topic · Due 21 October 2026

A desktop application with a **Tkinter graphical interface** storing its data
in **MySQL**: patients, departments, doctors, weekly shifts, appointments
with free-slot booking, medical records, prescriptions with stock control,
invoices, receipts and reports.

## 1. Install

```bash
pip install mysql-connector-python
```

Python 3.10 or later. Tkinter ships with Python on Windows and macOS; on
Ubuntu it is `sudo apt install python3-tk`.

## 2. Point it at your MySQL server

Open `config.py` and set your own user and password:

```python
MYSQL = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your password here",
    "database": "hospital_db",
}
```

## 3. Create the database and run

```bash
python setup_database.py    # creates hospital_db, all 11 tables, the view, the admin account
python seed_data.py         # demo data for testing and the presentation
python main.py              # starts the graphical interface
```

`setup_database.py` runs `CREATE DATABASE IF NOT EXISTS`, so an empty MySQL
server is enough. The SQL itself is in `data/schema_mysql.sql`.

## 4. Logins created by the seed script

| Username | Password | Role | Sees |
|---|---|---|---|
| admin | admin123 | admin | everything, including income reports and the audit log |
| reception1 | recep123 | receptionist | patients, bookings, payments; no income reports |
| drratha | doctor123 | doctor | only their own appointments |

## 5. The screens

**Sign in** → **dashboard** with five live counters, then one tab per area:

| Tab | What you can do |
|---|---|
| Patients | register, search by ID, name or phone, update, delete, visit history |
| Appointments | book from a list of genuinely free slots, cancel, no-show, complete a visit, view the receipt |
| Doctors | departments, doctors, activate/deactivate, weekly shifts that generate the slots |
| Billing & pharmacy | unpaid invoices, take payment, medicine stock, restock, low-stock and expiry warnings |
| Reports | seven reports, each exportable to CSV |
| Users | staff accounts and roles (admin only) |

Completing a visit is one window: medical record → prescriptions (stock drops
as you add them) → invoice → payment → printed receipt.

## 6. Testing

```bash
python tests/check_sql.py    # schema and SQL consistency, no server needed
python tests/run_tests.py    # the 34 test cases from the PRD
python tests/gui_smoke.py    # builds and drives every screen with no display
```

`tests/run_tests.py` and `tests/gui_smoke.py` rebuild the demo database
first, so never point them at data you want to keep. They run against
whichever backend `config.py` names.

`tests/fake_tk/` is a stand-in for tkinter used only by `gui_smoke.py`, so
the interface can be checked on a machine with no tkinter and no screen.
Nothing in the application imports it.

## 7. Files

```
hospital_system/
├── main.py                       starts the GUI
├── setup_database.py             creates the MySQL database and tables
├── config.py                     MySQL settings
├── seed_data.py                  demo data
├── cli_main.py                   the earlier text version, still working
├── gui/
│   ├── app.py                    main window, dashboard, tabs by role
│   ├── login_window.py           sign in, three attempts
│   ├── widgets.py                theme, data table, form dialog, receipt window
│   ├── patients_tab.py           Person 2
│   ├── doctors_tab.py            Person 3, includes the shift window
│   ├── appointments_tab.py       Person 4, booking and complete-visit windows
│   ├── billing_tab.py            invoices and pharmacy
│   ├── reports_tab.py            reports and CSV export
│   └── users_tab.py              accounts (admin only)
├── models/models.py              Person, Patient, Doctor, Department,
│                                 Schedule, Appointment, Invoice, Medicine
├── services/                     all the rules; no screen code at all
│   ├── auth_service.py           login, SHA-256 hashing, roles, audit log
│   ├── patient_service.py        patient CRUD, search, history
│   ├── doctor_service.py         departments, doctors, shifts, free slots
│   ├── appointment_service.py    booking rules, cancel, complete, records
│   ├── billing_service.py        invoices, payments, medicines, prescriptions
│   └── report_service.py         reports and CSV export
├── utils/
│   ├── database.py               the only module that talks to MySQL
│   ├── validator.py              one set of rules for both interfaces
│   └── receipt.py                receipt layout and text file output
├── data/
│   ├── schema_mysql.sql          the MySQL design
│   ├── schema_sqlite.sql         same design, offline fallback
│   ├── receipts/                 one text file per printed receipt
│   └── reports/                  CSV exports
└── tests/                        check_sql.py, run_tests.py, gui_smoke.py
```

## 8. Where each course concept lives

| Concept | File and place |
|---|---|
| Classes and objects | `models/models.py` |
| Inheritance | `Patient(Person)` and `Doctor(Person)` |
| Method overriding | `display_info()` redefined in both subclasses |
| Encapsulation | `_age`, `_phone`, `_fee` behind validating properties |
| Modules | `gui/`, `services/`, `utils/`, each imported where needed |
| Exception handling | one error class per service, caught by every screen |
| File handling | `utils/receipt.py`, `report_service.export_csv` |
| Date and time | `doctor_service.free_slots`, `validator.is_past` |
| Randomization | `seed_data.py` |
| Database | `utils/database.py` with MySQL, 11 tables, 1 view |
| GUI | `gui/`, Tkinter with ttk widgets |

## 9. Four design points worth defending in the presentation

**The interface is separable from the rules.** Not one line of SQL or
business logic sits in `gui/`, and not one Tkinter import sits in
`services/`. The proof is `cli_main.py`: the old text interface still runs
on exactly the same services.

**Double booking is blocked by MySQL itself, not only by Python.** MySQL has
no partial index, so `appointments` carries a generated column that is 1
while a visit is live and NULL once it is cancelled, inside a unique key on
`(doctor_id, date, time, active_slot)`. A unique key ignores NULLs, so a
cancelled visit keeps its row in history while its slot becomes bookable
again. Test T-11 and T-14 prove both halves.

**Prices are frozen when the transaction happens.** `appointments.fee` and
`prescriptions.unit_price` copy the price in force that day, so raising a
doctor's fee next month never rewrites an old receipt (test T-17).

**One set of validation rules serves both interfaces.** `utils/validator.py`
holds `parse_age`, `parse_phone`, `parse_date` and the rest; the GUI forms
and the old command-line prompts both call them, so a rule can never drift
between the two.
