from __future__ import annotations

import sqlite3


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS TB_PRODUCTION (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                work_date        TEXT,
                shift            TEXT,
                process_level1   TEXT,
                process_level2   TEXT,
                process_level3   TEXT,
                machine          TEXT,
                product          TEXT,
                worker           TEXT,
                plan_qty         REAL,
                actual_qty       REAL,
                work_time        REAL,
                efficiency       REAL,
                cycle_time       REAL,
                source_row_count INTEGER,
                created_at       TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS TB_DOWNTIME (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                production_id INTEGER,
                cause         TEXT,
                duration      REAL,
                row_index     INTEGER,
                FOREIGN KEY (production_id) REFERENCES TB_PRODUCTION(id)
            );

            CREATE TABLE IF NOT EXISTS TB_NONCONFORMITY (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                production_id INTEGER,
                cause         TEXT,
                qty           INTEGER,
                row_index     INTEGER,
                FOREIGN KEY (production_id) REFERENCES TB_PRODUCTION(id)
            );

            CREATE TABLE IF NOT EXISTS TB_DEFECT (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                production_id INTEGER,
                cause         TEXT,
                qty           INTEGER,
                row_index     INTEGER,
                FOREIGN KEY (production_id) REFERENCES TB_PRODUCTION(id)
            );

            CREATE TABLE IF NOT EXISTS TB_WARNING (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                production_id INTEGER,
                warning_code  TEXT,
                message       TEXT,
                FOREIGN KEY (production_id) REFERENCES TB_PRODUCTION(id)
            );

            CREATE INDEX IF NOT EXISTS idx_prod_date    ON TB_PRODUCTION(work_date);
            CREATE INDEX IF NOT EXISTS idx_prod_machine ON TB_PRODUCTION(machine);
            CREATE INDEX IF NOT EXISTS idx_dt_cause     ON TB_DOWNTIME(cause);
        """)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db("fom.db")
