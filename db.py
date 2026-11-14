import json
import sqlite3
from datetime import datetime

DB_PATH = "ledger.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            plan TEXT NOT NULL DEFAULT 'free'
        );
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            item TEXT,
            quantity REAL,
            total REAL NOT NULL,
            customer TEXT,
            amount_paid REAL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pending (
            user_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        );
        """)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists


def get_or_create_user(user_id):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def add_entry(user_id, e):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO entries
               (user_id, type, item, quantity, total, customer, amount_paid, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, e["type"], e["item"], e["quantity"], e["total"],
             e["customer"], e["amount_paid"], datetime.now().isoformat()),
        )


def set_pending(user_id, entries):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pending (user_id, data) VALUES (?, ?)",
            (user_id, json.dumps(entries)),
        )


def pop_pending(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT data FROM pending WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM pending WHERE user_id = ?", (user_id,))
        return json.loads(row["data"])


def get_debts(user_id):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT MIN(customer) AS customer,
                      SUM(owed) AS owed,
                      MIN(since) AS since
               FROM (
                   SELECT customer, total - amount_paid AS owed, created_at AS since
                   FROM entries
                   WHERE user_id = ? AND type = 'sale'
                     AND customer IS NOT NULL AND amount_paid < total
                   UNION ALL
                   SELECT customer, -total AS owed, NULL AS since
                   FROM entries
                   WHERE user_id = ? AND type = 'payment' AND customer IS NOT NULL
               )
               GROUP BY LOWER(customer)
               HAVING SUM(owed) > 0
               ORDER BY owed DESC""",
            (user_id, user_id),
        ).fetchall()
        return [dict(r) for r in rows]


def set_plan(user_id, plan, customer_id=None):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
        if customer_id:
            conn.execute(
                "UPDATE users SET plan = ?, stripe_customer_id = ? WHERE id = ?",
                (plan, customer_id, user_id),
            )
        else:
            conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))


def set_plan_by_customer(customer_id, plan):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET plan = ? WHERE stripe_customer_id = ?",
            (plan, customer_id),
        )


if __name__ == "__main__":
    init_db()
    get_or_create_user("test")
    add_entry("test", {"type": "sale", "item": "rice", "quantity": 2,
                       "total": 90000, "customer": "Mama Chidi", "amount_paid": 50000})
    print(get_debts("test"))