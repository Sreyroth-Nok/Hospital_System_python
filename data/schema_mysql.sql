-- ============================================================
--  Hospital Appointment & Patient Management System
--  MySQL 8.0 schema
--  Create the database first:
--      CREATE DATABASE hospital_db CHARACTER SET utf8mb4;
-- ============================================================

CREATE TABLE IF NOT EXISTS departments (
    id       VARCHAR(6)  NOT NULL,
    name     VARCHAR(60) NOT NULL,
    location VARCHAR(80),
    phone    VARCHAR(15),
    PRIMARY KEY (id),
    UNIQUE KEY uq_department_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS doctors (
    id             VARCHAR(6)  NOT NULL,
    department_id  VARCHAR(6)  NOT NULL,
    name           VARCHAR(60) NOT NULL,
    gender         CHAR(1),
    age            INT,
    phone          VARCHAR(15),
    specialization VARCHAR(60),
    fee            DECIMAL(10,2) NOT NULL DEFAULT 0,
    is_active      TINYINT NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    KEY idx_doctor_dept (department_id),
    CONSTRAINT fk_doctor_dept FOREIGN KEY (department_id) REFERENCES departments(id),
    CONSTRAINT chk_doctor_gender CHECK (gender IN ('M','F')),
    CONSTRAINT chk_doctor_age    CHECK (age BETWEEN 20 AND 90),
    CONSTRAINT chk_doctor_fee    CHECK (fee >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS users (
    username         VARCHAR(30)  NOT NULL,
    password_hash    VARCHAR(64)  NOT NULL,
    role             VARCHAR(15)  NOT NULL,
    linked_doctor_id VARCHAR(6)   DEFAULT NULL,
    is_active        TINYINT      NOT NULL DEFAULT 1,
    created_at       VARCHAR(20)  NOT NULL,
    PRIMARY KEY (username),
    KEY idx_user_doctor (linked_doctor_id),
    CONSTRAINT fk_user_doctor FOREIGN KEY (linked_doctor_id) REFERENCES doctors(id),
    CONSTRAINT chk_user_role CHECK (role IN ('admin','receptionist','doctor'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS patients (
    id         VARCHAR(6)   NOT NULL,
    name       VARCHAR(60)  NOT NULL,
    gender     CHAR(1),
    age        INT,
    phone      VARCHAR(15)  NOT NULL,
    address    VARCHAR(120),
    blood_type VARCHAR(5),
    allergies  VARCHAR(120),
    created_at VARCHAR(20)  NOT NULL,
    PRIMARY KEY (id),
    KEY idx_patient_name (name),
    CONSTRAINT chk_patient_gender CHECK (gender IN ('M','F')),
    CONSTRAINT chk_patient_age    CHECK (age BETWEEN 0 AND 120)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dates and times are stored as text in the same format the application
-- uses everywhere (YYYY-MM-DD and HH:MM). Keeping one format end to end
-- removes every conversion between Python and the database.
CREATE TABLE IF NOT EXISTS appointments (
    id          VARCHAR(6)  NOT NULL,
    patient_id  VARCHAR(6)  NOT NULL,
    doctor_id   VARCHAR(6)  NOT NULL,
    created_by  VARCHAR(30) NOT NULL,
    `date`      VARCHAR(10) NOT NULL,
    `time`      VARCHAR(5)  NOT NULL,
    reason      VARCHAR(120),
    status      VARCHAR(10) NOT NULL DEFAULT 'Booked',
    fee         DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at  VARCHAR(20) NOT NULL,
    -- MySQL has no partial index, so this generated column is 1 while the
    -- visit is live and NULL once it is cancelled. A UNIQUE key ignores
    -- NULLs, so the slot is blocked while booked and free again after a
    -- cancellation, and the cancelled row stays in history.
    active_slot TINYINT GENERATED ALWAYS AS
                (CASE WHEN status IN ('Booked','Completed') THEN 1 ELSE NULL END) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY uq_active_slot (doctor_id, `date`, `time`, active_slot),
    KEY idx_appt_date (`date`),
    KEY idx_appt_patient (patient_id),
    KEY idx_appt_doctor (doctor_id),
    CONSTRAINT fk_appt_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_appt_doctor  FOREIGN KEY (doctor_id)  REFERENCES doctors(id),
    CONSTRAINT fk_appt_user    FOREIGN KEY (created_by) REFERENCES users(username),
    CONSTRAINT chk_appt_status CHECK (status IN ('Booked','Completed','Cancelled','No-show')),
    CONSTRAINT chk_appt_fee    CHECK (fee >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS schedules (
    id           VARCHAR(6) NOT NULL,
    doctor_id    VARCHAR(6) NOT NULL,
    day_of_week  CHAR(3)    NOT NULL,
    start_time   VARCHAR(5) NOT NULL,
    end_time     VARCHAR(5) NOT NULL,
    slot_minutes INT        NOT NULL DEFAULT 30,
    PRIMARY KEY (id),
    UNIQUE KEY uq_shift (doctor_id, day_of_week, start_time),
    CONSTRAINT fk_shift_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id),
    CONSTRAINT chk_shift_day CHECK (day_of_week IN ('Mon','Tue','Wed','Thu','Fri','Sat','Sun'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS records (
    id             VARCHAR(6)  NOT NULL,
    appointment_id VARCHAR(6)  NOT NULL,
    symptoms       VARCHAR(255),
    diagnosis      VARCHAR(255),
    treatment      VARCHAR(255),
    notes          VARCHAR(255),
    follow_up_date VARCHAR(10) DEFAULT NULL,
    created_at     VARCHAR(20) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_record_visit (appointment_id),
    CONSTRAINT fk_record_appt FOREIGN KEY (appointment_id) REFERENCES appointments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS invoices (
    id             VARCHAR(8)  NOT NULL,
    appointment_id VARCHAR(6)  NOT NULL,
    consult_fee    DECIMAL(10,2) NOT NULL DEFAULT 0,
    medicine_total DECIMAL(10,2) NOT NULL DEFAULT 0,
    service_fee    DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount       DECIMAL(10,2) NOT NULL DEFAULT 0,
    grand_total    DECIMAL(10,2) NOT NULL DEFAULT 0,
    payment_status VARCHAR(10) NOT NULL DEFAULT 'Unpaid',
    payment_method VARCHAR(15) DEFAULT NULL,
    paid_at        VARCHAR(20) DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_invoice_visit (appointment_id),
    CONSTRAINT fk_invoice_appt FOREIGN KEY (appointment_id) REFERENCES appointments(id),
    CONSTRAINT chk_pay_status CHECK (payment_status IN ('Unpaid','Paid','Refunded'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS medicines (
    id          VARCHAR(6)  NOT NULL,
    name        VARCHAR(60) NOT NULL,
    category    VARCHAR(40),
    unit        VARCHAR(15),
    unit_price  DECIMAL(10,2) NOT NULL DEFAULT 0,
    stock_qty   INT NOT NULL DEFAULT 0,
    reorder_at  INT NOT NULL DEFAULT 10,
    expiry_date VARCHAR(10),
    PRIMARY KEY (id),
    UNIQUE KEY uq_medicine_name (name),
    CONSTRAINT chk_med_price CHECK (unit_price >= 0),
    CONSTRAINT chk_med_stock CHECK (stock_qty >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS prescriptions (
    id          VARCHAR(8) NOT NULL,
    record_id   VARCHAR(6) NOT NULL,
    medicine_id VARCHAR(6) NOT NULL,
    dosage      VARCHAR(60),
    quantity    INT NOT NULL,
    unit_price  DECIMAL(10,2) NOT NULL,
    line_total  DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_pres_record (record_id),
    CONSTRAINT fk_pres_record   FOREIGN KEY (record_id)   REFERENCES records(id),
    CONSTRAINT fk_pres_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id),
    CONSTRAINT chk_pres_qty CHECK (quantity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS audit_log (
    id        INT NOT NULL AUTO_INCREMENT,
    username  VARCHAR(30)  NOT NULL,
    action    VARCHAR(160) NOT NULL,
    timestamp VARCHAR(20)  NOT NULL,
    PRIMARY KEY (id),
    KEY idx_audit_user (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- One row per appointment with every name already joined in, so report
-- queries in Python stay one line long.
CREATE OR REPLACE VIEW v_appointment_full AS
SELECT a.id            AS appointment_id,
       a.`date`        AS `date`,
       a.`time`        AS `time`,
       a.status        AS status,
       a.fee           AS fee,
       p.id            AS patient_id,
       p.name          AS patient_name,
       p.age           AS patient_age,
       d.id            AS doctor_id,
       d.name          AS doctor_name,
       d.specialization AS specialization,
       dp.name         AS department,
       i.grand_total   AS grand_total,
       i.payment_status AS payment_status
FROM appointments a
JOIN patients    p  ON p.id  = a.patient_id
JOIN doctors     d  ON d.id  = a.doctor_id
JOIN departments dp ON dp.id = d.department_id
LEFT JOIN invoices i ON i.appointment_id = a.id;
