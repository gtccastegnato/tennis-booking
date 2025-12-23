from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3
import os
import stripe
from datetime import datetime, timedelta

app = Flask(__name__)

# ======================
# CONFIG
# ======================
app.secret_key = os.environ.get(
    "ADMIN_SECRET_KEY",
    "98dsf7sd98f7sd98fsd98f7sdf"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "Porcodio.1994"
)

DATABASE = "bookings.db"

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

# ======================
# INDEX
# ======================
@app.route("/")
def index():
    return render_template(
        "index.html",
        STRIPE_PUBLISHABLE_KEY=os.environ.get("STRIPE_PUBLISHABLE_KEY")
    )

# ======================
# SLOT DISPONIBILI
# ======================
@app.route("/slots")
def slots():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify([])

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")

    # Limite date
    if not (datetime(2026, 4, 1) <= date_obj <= datetime(2026, 7, 31)):
        return jsonify([])

    weekday = date_obj.weekday()  # 0 lunedì

    if weekday < 5:
        start_h, end_h = "17:30", "20:30"
    else:
        start_h, end_h = "09:00", "17:00"

    slots = []
    t = datetime.combine(date_obj, datetime.strptime(start_h, "%H:%M").time())
    end_t = datetime.combine(date_obj, datetime.strptime(end_h, "%H:%M").time())

    while t < end_t:
        slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=60)

    db = get_db()
    cur = db.cursor()
    now = datetime.now()

    # libera slot scaduti
    cur.execute("""
        UPDATE bookings
        SET reserved_until = NULL
        WHERE reserved_until IS NOT NULL
        AND reserved_until < ?
        AND paid = 0
    """, (now,))
    db.commit()

    cur.execute("""
        SELECT time FROM bookings
        WHERE date = ?
        AND (paid = 1 OR reserved_until > ?)
    """, (date_str, now))

    booked = [r["time"] for r in cur.fetchall()]
    db.close()

    available = [s for s in slots if s not in booked]
    return jsonify(available)

# ======================
# PRENOTAZIONE
# ======================
@app.route("/reserve", methods=["POST"])
def reserve():
    data = request.json

    date = data.get("date")
    time = data.get("time")
    name = data.get("name")
    phone = data.get("phone")
    email = data.get("email")

    if not all([date, time, name, phone, email]):
        return jsonify({"error": "Dati mancanti"}), 400

    db = get_db()
    cur = db.cursor()

    cur.execute("""
        INSERT INTO bookings
        (date, time, name, phone, email, paid, reserved_until)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    """, (
        date,
        time,
        name,
        phone,
        email,
        datetime.now() + timedelta(minutes=10)
    ))

    booking_id = cur.lastrowid
    db.commit()
    db.close()

    return jsonify({"booking_id": booking_id})

# ======================
# STRIPE CHECKOUT
# ======================
@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    data = request.json
    booking_id = data.get("booking_id")

    if not booking_id:
        return jsonify({"error": "booking_id mancante"}), 400

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "Caparra campo tennis"},
                "unit_amount": 1000
            },
            "quantity": 1
        }],
        success_url=request.host_url + "?success=1",
        cancel_url=request.host_url + "?cancel=1",
        metadata={"booking_id": booking_id}
    )

    return jsonify({"url": session.url})


# ======================
if __name__ == "__main__":
    app.run(debug=True)

@app.route("/stripe-health")
def stripe_health():
    try:
        account = stripe.Account.retrieve()
        return jsonify({
            "ok": True,
            "charges_enabled": account.get("charges_enabled"),
            "payouts_enabled": account.get("payouts_enabled"),
            "details_submitted": account.get("details_submitted"),
            "country": account.get("country"),
            "business_type": account.get("business_type")
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500
        # ======================
# ADMIN
# ======================
def admin_required():
    return session.get("admin_logged") is True

@app.route("/admin")
def admin():
    if not admin_required():
        return redirect("/admin-login")
    return render_template("admin.html")

@app.route("/admin/bookings")
def admin_bookings():
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT id, date, time, name, phone, email, paid
        FROM bookings
        ORDER BY date, time
    """)
    rows = [dict(r) for r in cur.fetchall()]
    db.close()
    return jsonify(rows)

@app.route("/admin/delete/<int:booking_id>", methods=["POST"])
def admin_delete(booking_id):
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin_logged"] = True
            return redirect("/admin")
        else:
            return "Password errata", 401

    return """
    <h2>Login Admin</h2>
    <form method="post">
        <input type="password" name="password" placeholder="Password admin">
        <button type="submit">Entra</button>
    </form>
    """

@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect("/")
