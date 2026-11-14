import json
import os
from typing import Literal, Optional

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel

load_dotenv()
client = Groq()
MODEL = os.getenv("MODEL", "openai/gpt-oss-120b")


class Entry(BaseModel):
    type: Literal["sale", "expense", "Payment"]
    item: str
    quantity: float = 1
    total: float
    customer: Optional[str] = None
    amount_paid: Optional[float] = None


SYSTEM = """You extract bookkeeping entries from messages written by Nigerian
market traders, in English or Pidgin. Return ONLY JSON, no prose, in this shape:
{"entries": [{"type": "sale|expense", "item": str, "quantity": number,
"total": number in naira, "customer": str|null, "amount_paid": number|null}]}
Rules:
- "45k" means 45000. "2 bags rice 45k each" has total 90000.
- "I buy", "I pay", "transport", "rent" are expenses. "I sell", "sold" are sales.
- For expenses, amount_paid equals total.
- For sales, amount_paid is null unless the message says how much was paid.
- A customer paying off an old debt ("Mama Chidi pay me 40k", "Emeka don pay") is type "payment": item "payment", customer is the name, total is the amount.
- One message can contain several entries.
- "item" is the product name only, without units: "2 bags rice" gives item "rice"."""


def extract_entries(text: str) -> list[Entry]:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        reasoning_effort="low",
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    data = json.loads(raw)
    return [Entry(**e) for e in data["entries"]]


if __name__ == "__main__":
    tests = [
        "Sold 2 bags rice 45k each to Mama Chidi, she pay 50k",
        "I buy pepper twelve thousand, I pay transport two thousand five hundred",
    ]
    for t in tests:
        print(t)
        for e in extract_entries(t):
            print("  ", e)