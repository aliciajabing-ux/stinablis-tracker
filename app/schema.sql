-- WHAT THIS FILE DOES: Describes every table (think: every spreadsheet) the tracker keeps.
-- WHO CAN USE IT: Run once by setup_database.py. Nobody edits the live database by hand.
--
-- Plain-English rules used below:
--   TEXT    = words or codes such as "M001"
--   REAL    = numbers that can have decimals, such as 72.50
--   INTEGER = whole numbers; here 1 means "yes" and 0 means "no"
--   Dates are stored as text in UTC time. The screens show Malaysia time (UTC+8).

-- People who can log in. Role decides what they are allowed to do.
CREATE TABLE IF NOT EXISTS users (
    id                  TEXT PRIMARY KEY,
    username            TEXT NOT NULL UNIQUE,
    password_hash       TEXT,                     -- scrambled password, never plain text
    role                TEXT NOT NULL CHECK (role IN ('ADMIN', 'EMPLOYEE')),
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    failed_login_count  INTEGER NOT NULL DEFAULT 0,
    locked_until        TEXT                      -- empty unless the account is locked
);

-- Every material we keep in stock, such as PLA filament or resin.
CREATE TABLE IF NOT EXISTS materials (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    material_type       TEXT,
    colour              TEXT,
    unit                TEXT NOT NULL CHECK (unit IN ('g', 'ml', 'pcs')),
    quantity_on_hand    REAL NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    reorder_level       REAL NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Every shop or website we buy from, with contact details.
CREATE TABLE IF NOT EXISTS suppliers (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    supplier_type   TEXT NOT NULL CHECK (supplier_type IN ('LOCAL', 'ONLINE')),
    address         TEXT,
    phone           TEXT,
    email           TEXT,
    website         TEXT,
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- One row per "supplier X sells material Y, at this price, with this lead time".
-- Prices are per PACK (for example one 1 kg spool), not per gram.
-- Money is in MYR (Malaysian Ringgit).
CREATE TABLE IF NOT EXISTS supplier_offers (
    id                      TEXT PRIMARY KEY,
    supplier_id             TEXT NOT NULL REFERENCES suppliers(id),
    material_id             TEXT NOT NULL REFERENCES materials(id),
    pack_size               REAL NOT NULL CHECK (pack_size > 0),
    pack_unit               TEXT NOT NULL CHECK (pack_unit IN ('g', 'ml', 'pcs')),
    price_per_pack_myr      REAL NOT NULL CHECK (price_per_pack_myr >= 0),   -- Admin and Employee can see; only Admin can change
    minimum_order_packs     INTEGER NOT NULL DEFAULT 1 CHECK (minimum_order_packs >= 1),
    shipping_cost_myr       REAL NOT NULL DEFAULT 0 CHECK (shipping_cost_myr >= 0),  -- Admin and Employee can see; only Admin can change
    lead_time_days          INTEGER NOT NULL CHECK (lead_time_days >= 0),
    is_active               INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

-- Every change to stock. Rows are added, never edited or deleted.
CREATE TABLE IF NOT EXISTS stock_movements (
    id              TEXT PRIMARY KEY,
    material_id     TEXT NOT NULL REFERENCES materials(id),
    movement_type   TEXT NOT NULL CHECK (movement_type IN ('USED', 'RECEIVED', 'ADJUSTED')),
    quantity        REAL NOT NULL CHECK (quantity >= 0),
    note            TEXT,
    user_id         TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Who changed what, and when. Admins can read it. Nobody can edit it.
CREATE TABLE IF NOT EXISTS activity_log (
    id              TEXT PRIMARY KEY,
    user_id         TEXT REFERENCES users(id),
    action          TEXT NOT NULL,
    table_name      TEXT,
    record_id       TEXT,
    details         TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
