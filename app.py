
from flask import Flask, render_template, request, jsonify
import sqlite3, os, stripe
from datetime import datetime, timedelta

app = Flask(__name__)
DATABASE = "bookings.db"
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

@app.route("/")
def index():
    return render_template("index.html", STRIPE_PUBLISHABLE_KEY=os.environ.get("STRIPE_PUBLISHABLE_KEY"))

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/slots")
def slots():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify([])

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    if not (datetime(2026,4,1) <= date_obj <= datetime(2026,7,31)):
        return jsonify([])

    weekday = date_obj.weekday()
    start, end = ("17:30","19:30") if weekday < 5 else ("09:00","16:00")

    slots = []
    t = datetime.combine(date_obj, datetime.strptime(start, "%H:%M").time())
    end_t = datetime.combine(date_obj, datetime.strptime(end, "%H:%M").time())
    while t < end_t:
        slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=60)

    return jsonify(slots)

@app.route("/reserve", methods=["POST"])
def reserve():
    data = request.json
    return jsonify({"booking_id": 1})

@app.route("/create-payment-intent", methods=["POST"])
def create_payment_intent():
    intent = stripe.PaymentIntent.create(
        amount=1000,
        currency="eur",
        automatic_payment_methods={"enabled": True}
    )
    return jsonify({"client_secret": intent.client_secret})

if __name__ == "__main__":
    app.run(debug=True)
