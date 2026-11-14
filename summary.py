from datetime import datetime, timedelta

import db


def period_start(period):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "day":
        return today
    return today - timedelta(days=6)


def get_summary(user_id, period):
    start = period_start(period).isoformat()
    with db.get_conn() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM entries WHERE user_id = ? AND created_at >= ?",
                (user_id, start),
            )
        ]

    sales = [r for r in rows if r["type"] == "sale" and r["item"] != "credit"]
    expenses = [r for r in rows if r["type"] == "expense"]
    payments = [r for r in rows if r["type"] == "payment"]

    total_sales = sum(r["total"] for r in sales)
    total_expenses = sum(r["total"] for r in expenses)
    cash_in = sum(r["amount_paid"] or 0 for r in sales) + sum(r["total"] for r in payments)

    by_item = {}
    for r in sales:
        key = (r["item"] or "other").lower()
        by_item[key] = by_item.get(key, 0) + r["total"]
    best = max(by_item.items(), key=lambda kv: kv[1]) if by_item else None
    top_expense = max(expenses, key=lambda r: r["total"]) if expenses else None

    return {
        "count": len(rows),
        "sales": total_sales,
        "expenses": total_expenses,
        "profit": total_sales - total_expenses,
        "cash_in": cash_in,
        "best": best,
        "top_expense": top_expense,
    }