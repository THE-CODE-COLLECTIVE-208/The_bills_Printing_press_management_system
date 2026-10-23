-- Printing Shop Management System database (SQLite)

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE,
    full_name     TEXT    NOT NULL,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('attendant', 'manager')),
    active        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS services (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL UNIQUE,
    unit_price REAL    NOT NULL,
    icon       TEXT    NOT NULL DEFAULT '🖨️',
    active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    phone      TEXT UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY,
    queue_date    TEXT    NOT NULL,
    queue_no      INTEGER NOT NULL,
    track_code    TEXT    NOT NULL UNIQUE,
    customer_id   INTEGER NOT NULL REFERENCES customers (id),
    service_id    INTEGER NOT NULL REFERENCES services (id),
    quantity      INTEGER NOT NULL,
    unit_price    REAL    NOT NULL,
    amount        REAL    NOT NULL,
    notes         TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'Waiting',
    source        TEXT    NOT NULL,            -- 'Counter' or 'Check-in'
    created_by    INTEGER REFERENCES users (id),
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL,
    processing_at TEXT,
    ready_at      TEXT,
    completed_at  TEXT,
    cancelled_at  TEXT,
    UNIQUE (queue_date, queue_no)
);

CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders (id),
    amount      REAL    NOT NULL,
    method      TEXT    NOT NULL,
    received_by INTEGER REFERENCES users (id),
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments (order_id);
