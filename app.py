from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import stripe
from datetime import datetime, timedelta

app = Flask(__name__)

DATABASE = "bookings.db"

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

# --- INDEX ---
@app.route("/")
def index():
    return render_template("index.html", STRIPE_PUBLISHABLE_KEY=os.environ.get("STRIPE_PUBLISHABLE_KEY"))

# --- ADMIN ---
@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/admin/bookings")
def admin_bookings():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM bookings")
    rows = [dict(row) for row in cur.fetchall()]
    db.close()
    return jsonify(rows)

@app.route("/admin/delete/<int:booking_id>", methods=["POST"])
def admin_delete(booking_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    db.commit()
    db.close()
    return '', 200

# --- SLOT DISPONIBILI ---
@app.route("/slots")
def get_slots():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify([])

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = date_obj.weekday()  # 0=lunedì, 6=domenica

    # Slot: lun-ven 17:30-19:30, sab-dom 09:00-16:00
    slots = []
    if weekday < 5:
        start = datetime.combine(date_obj, datetime.strptime("17:30", "%H:%M").time())
        end = datetime.combine(date_obj, datetime.strptime("19:30", "%H:%M").time())
    else:
        start = datetime.combine(date_obj, datetime.strptime("09:00", "%H:%M").time())
        end = datetime.combine(date_obj, datetime.strptime("16:00", "%H:%M").time())

    current = start
    while current < end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=60)

    # Rimuovi slot scaduti/reservati
    db = get_db()
    cur = db.cursor()
    now = datetime.now()
    cur.execute("UPDATE bookings SET reserved_until=NULL WHERE reserved_until IS NOT NULL AND reserved_until<? AND paid=0", (now,))
    db.commit()

    cur.execute("SELECT time FROM bookings WHERE date=? AND (paid=1 OR reserved_until>?)", (date_str, now))
    booked = [row["time"] for row in cur.fetchall()]
    db.close()

    available = [s for s in slots if s not in booked]
    return jsonify(available)

# --- PRENOTAZIONE ---
@app.route("/reserve", methods=["POST"])
def reserve():
    data = request.json
    date = data.get("date")
    time = data.get("time")
    name = data.get("name")
    phone = data.get("phone")
    email = data.get("email")

    if not all([date, time, name, phone, email]):
        return jsonify({"error": "Compila tutti i campi"}), 400

    db = get_db()
    cur = db.cursor()
    reserved_until = datetime.now() + timedelta(minutes=10)
    cur.execute(
        "INSERT INTO bookings (date, time, name, phone, email, paid, reserved_until) VALUES (?,?,?,?,?,?,?)",
        (date, time, name, phone, email, 0, reserved_until)
    )
    booking_id = cur.lastrowid
    db.commit()
    db.close()

    return jsonify({"booking_id": booking_id})

# --- STRIPE PAYMENT ---
@app.route("/create-payment-intent", methods=["POST"])
def create_payment_intent():
    data = request.json
    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"error": "booking_id mancante"}), 400

    intent = stripe.PaymentIntent.create(
        amount=1000,  # 10 euro in centesimi
        currency="eur",
        automatic_payment_methods={"enabled": True},
        metadata={"booking_id": booking_id}
    )
    return jsonify({"client_secret": intent.client_secret})

@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        return str(e), 400

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        booking_id = intent["metadata"].get("booking_id")
        if booking_id:
            db = get_db()
            cur = db.cursor()
            cur.execute("UPDATE bookings SET paid=1, reserved_until=NULL WHERE id=?", (booking_id,))
            db.commit()
            db.close()

    return "", 200

if __name__ == "__main__":
    app.run(debug=True)
