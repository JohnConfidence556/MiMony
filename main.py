from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

import db
from extractor import extract_entries

app = FastAPI()
db.init_db()

DEBT_WORDS = ("who owe", "who owes", "debt", "owing")


class ChatIn(BaseModel):
    user_id: str
    message: str


def naira(n):
    return f"₦{n:,.0f}"


def parse_amount(text):
    import re
    m = re.search(r"(\d[\d,]*\.?\d*)\s*(k)?", text.lower())
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    return n * 1000 if m.group(2) else n


def describe(e):
    if e["type"] == "payment":
        return f"Payment from {e['customer']}, {naira(e['total'])}"
    return f"{e['type'].capitalize()}, {e['quantity']:g} × {e['item']}, {naira(e['total'])}"


def ask(e):
    return f"{describe(e)}. Did {e['customer']} pay? (Yes / No / amount)"


def debts_reply(user):
    debts = db.get_debts(user["id"])
    if not debts:
        return "Nobody owes you right now."
    total = sum(d["owed"] for d in debts)
    lines = [f"{len(debts)} customer(s) owe you {naira(total)} in total:"]
    for d in debts:
        days = (datetime.now() - datetime.fromisoformat(d["since"])).days
        lines.append(f"{d['customer']} {naira(d['owed'])} ({days} days)")
    if user["plan"] == "free":
        lines.append("Upgrade to Premium and I will remind them for you.")
    return "\n".join(lines)


def resolve_pending(user_id, text):
    queue = db.pop_pending(user_id)
    if queue is None:
        return None
    e = queue.pop(0)
    t = text.lower().strip()
    amount = parse_amount(t)
    if amount is not None:
        e["amount_paid"] = min(amount, e["total"])
    elif t.startswith(("yes", "paid")):
        e["amount_paid"] = e["total"]
    elif t.startswith("no"):
        e["amount_paid"] = 0
    else:
        db.set_pending(user_id, [e] + queue)
        return "Sorry, did they pay? Reply Yes, No, or the amount, like 50k."
    db.add_entry(user_id, e)
    reply = f"Done. {describe(e)}. Paid {naira(e['amount_paid'])}."
    owed = e["total"] - e["amount_paid"]
    if owed > 0:
        reply += f" {e['customer']} owes {naira(owed)}."
    if queue:
        db.set_pending(user_id, queue)
        reply += "\n" + ask(queue[0])
    return reply


@app.post("/chat")
def chat(body: ChatIn):
    user = db.get_or_create_user(body.user_id)
    text = body.message.strip()

    reply = resolve_pending(body.user_id, text)
    if reply:
        return {"reply": reply}

    if any(w in text.lower() for w in DEBT_WORDS):
        return {"reply": debts_reply(user)}

    try:
        entries = [e.model_dump() for e in extract_entries(text)]
    except Exception:
        entries = []
    if not entries:
        return {"reply": "Sorry, I didn't get that. Try: Sold 2 bags rice 45k each"}

    logged, to_ask = [], []
    for e in entries:
        if e["type"] == "sale" and e["amount_paid"] is None:
            if e["customer"]:
                to_ask.append(e)
                continue
            e["amount_paid"] = e["total"]
        if e["type"] != "sale" and e["amount_paid"] is None:
            e["amount_paid"] = e["total"]
        db.add_entry(body.user_id, e)
        logged.append(describe(e))

    parts = []
    if logged:
        parts.append("Logged:\n" + "\n".join(logged))
    if to_ask:
        db.set_pending(body.user_id, to_ask)
        parts.append(ask(to_ask[0]))
    return {"reply": "\n".join(parts)}