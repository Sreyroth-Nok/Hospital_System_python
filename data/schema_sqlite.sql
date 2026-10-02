-- ============================================================
--  Hospital Appointment & Patient Management System
--  SQLite schema
-- ============================================================

PRAGMA foreign_keys = ON;

-- ---------- TIER 1 : CORE ----------------------------------

CREATE TABLE IF NOT EXISTS departments (
    id       TEXT PRIMARY KEY,              -- DP01
    name     TEXT NOT NULL UNIQUE,
    location TEXT,
    phone    TEXT
);

CREATE TABLE IF NOT EXISTS doctors (
    id             TEXT PRIMARY KEY,        -- D001
    department_id  TEXT NOT NULL,
    name           TEXT NOT NULL,
    gender         TEXT CHECK (gender IN ('M','F')),
    age            INTEGER CHECK (age BETWEEN 20 AND 90),
    phone          TEXT,
    specialization TEXT,
    fee            REAL NOT NULL CHECK (fee >= 0),
    is_active      INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS users (
    username         TEXT PRIMARY KEY,
    password_hash    TEXT NOT NULL,
    role             TEXT NOT NULL CHECK (role IN ('admin','receptionist','doctor')),
    linked_doctor_id TEXT,                  -- only for role = 'doctor'
    is_active        INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT NOT NULL,
    FOREIGN KEY (linked_doctor_id) REFERENCES doctors(id)
);

CREATE TABLE IF NOT EXISTS patients (
    id         TEXT PRIMARY KEY,            -- P001
    name       TEXT NOT NULL,
    gender     TEXT CHECK (gender IN ('M','F')),
    age        INTEGER CHECK (age BETWEEN 0 AND 120),
    phone      TEXT NOT NULL,
    address    TEXT,
    blood_type TEXT,
    allergies  TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS appointments (
    id         TEXT PRIMARY KEY,            -- A001
    patient_id TEXT NOT NULL,
    doctor_id  TEXT NOT NULL,
    created_by TEXT NOT NULL,               -- which user booked it
    date       TEXT NOT NULL,               -- YYYY-MM-DD
    time       TEXT NOT NULL,               -- HH:MM
    reason     TEXT,
    status     TEXT NOT NULL DEFAULT 'Booked'
               CHECK (status IN ('Booked','Completed','Cancelled','No-show')),
    fee        REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),  -- frozen at booking time
    created_at TEXT NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (doctor_id)  REFERENCES doctors(id),
    FOREIGN KEY (created_by) REFERENCES users(username)
);

-- Blocks double booking. A partial index, so a Cancelled or No-show visit
-- keeps its row in history while the slot becomes bookable again.
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_slot
    ON appointments(doctor_id, date, time)
    WHERE status IN ('Booked','Completed');

-- ---------- TIER 2 : IMPORTANT -----------------------------

CREATE TABLE IF NOT EXISTS schedules (
    id            TEXT PRIMARY KEY,         -- S001
    doctor_id     TEXT NOT NULL,
    day_of_week   TEXT NOT NULL
                  CHECK (day_of_week IN ('Mon','Tue','Wed','Thu','Fri','Sat','Sun')),
    start_time    TEXT NOT NULL,            -- 08:00
    end_time      TEXT NOT NULL,            -- 12:00
    slot_minutes  INTEGER NOT NULL DEFAULT 30,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id),
    UNIQUE (doctor_id, day_of_week, start_time)
);

CREATE TABLE IF NOT EXISTS records (
    id             TEXT PRIMARY KEY,        -- R001
    appointment_id TEXT NOT NULL UNIQUE,    -- UNIQUE = one record per visit
    symptoms       TEXT,
    diagnosis      TEXT,
    treatment      TEXT,
    notes          TEXT,
    follow_up_date TEXT,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id              TEXT PRIMARY KEY,       -- INV001
    appointment_id  TEXT NOT NULL UNIQUE,
    consult_fee     REAL NOT NULL DEFAULT 0,
    medicine_total  REAL NOT NULL DEFAULT 0,
    service_fee     REAL NOT NULL DEFAULT 0,
    discount        REAL NOT NULL DEFAULT 0,
    grand_total     REAL NOT NULL DEFAULT 0,
    payment_status  TEXT NOT NULL DEFAULT 'Unpaid'
                    CHECK (payment_status IN ('Unpaid','Paid','Refunded')),
    payment_method  TEXT,
    paid_at         TEXT,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id)
);

-- ---------- TIER 3 : BONUS ---------------------------------

CREATE TABLE IF NOT EXISTS medicines (
    id          TEXT PRIMARY KEY,           -- M001
    name        TEXT NOT NULL UNIQUE,
    category    TEXT,
    unit        TEXT,                       -- tablet, bottle, box
    unit_price  REAL NOT NULL CHECK (unit_price >= 0),
    stock_qty   INTEGER NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    reorder_at  INTEGER NOT NULL DEFAULT 10,
    expiry_date TEXT
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id           TEXT PRIMARY KEY,          -- PR001
    record_id    TEXT NOT NULL,
    medicine_id  TEXT NOT NULL,
    dosage       TEXT,                      -- "1 tablet after meal"
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    unit_price   REAL NOT NULL,             -- frozen price at time of issue
    line_total   REAL NOT NULL,
    FOREIGN KEY (record_id)   REFERENCES records(id),
    FOREIGN KEY (medicine_id) REFERENCES medicines(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    username  TEXT NOT NULL,
    action    TEXT NOT NULL,                -- "DELETE patient P003"
    timestamp TEXT NOT NULL,
    FOREIGN KEY (username) REFERENCES users(username)
);

-- ---------- INDEXES (speed up common searches) --------------

CREATE INDEX IF NOT EXISTS idx_appt_date    ON appointments(date);
CREATE INDEX IF NOT EXISTS idx_appt_patient ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appt_doctor  ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_patient_name ON patients(name);
CREATE INDEX IF NOT EXISTS idx_doctor_dept  ON doctors(department_id);

-- ---------- VIEW (makes reports one line of Python) ---------

CREATE VIEW IF NOT EXISTS v_appointment_full AS
SELECT a.id            AS appointment_id,
       a.date, a.time, a.status,
       p.id            AS patient_id,
       p.name          AS patient_name,
       p.age           AS patient_age,
       d.id            AS doctor_id,
       d.name          AS doctor_name,
       d.specialization,
       dp.name         AS department,
       i.grand_total,
       i.payment_status
FROM appointments a
JOIN patients    p  ON p.id  = a.patient_id
JOIN doctors     d  ON d.id  = a.doctor_id
JOIN departments dp ON dp.id = d.department_id
LEFT JOIN invoices i ON i.appointment_id = a.id;
