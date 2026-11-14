import os

import stripe
from dotenv import load_dotenv

import db

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
PRICE_ID = os.getenv("STRIPE_PRICE_ID")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")


def upgrade_link(user_id):
    return f"{BASE_URL}/upgrade/{user_id}"


def create_checkout_url(user_id):
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        client_reference_id=user_id,
        success_url=f"{BASE_URL}/?paid=1",
        cancel_url=f"{BASE_URL}/",
    )
    return session.url


def handle_event(payload, sig_header):
    event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    obj = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        db.set_plan(obj["client_reference_id"], "premium", obj["customer"])
        print("PREMIUM ON:", obj["client_reference_id"])

    elif event["type"] == "customer.subscription.deleted":
        db.set_plan_by_customer(obj["customer"], "free")
        print("PREMIUM OFF:", obj["customer"])