

import os
import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


from flask import Flask, render_template, request, jsonify
import sqlite3
import smtplib
import time
from datetime import datetime, timedelta

app = Flask(__name__)
DATABASE = "bookings.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    return conn

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS bookings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            name TEXT,
            phone TEXT,
            email TEXT,
            paid INTEGER DEFAULT 0,
            reserved_until INTEGER DEFAULT NULL
        )
    """)
    db.commit()
    db.close()

# --------------------------
# Routes principali
# --------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
def admin():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, date, time, name, phone, email, paid FROM bookings ORDER BY date,time")
    bookings = cur.fetchall()
    db.close()
    return render_template("admin.html", bookings=bookings)

# --------------------------
# Prenotazioni
# --------------------------
@app.route("/reserve", methods=["POST"])
def reserve():
    data = request.json
    date = data.get("date")
    time_slot = data.get("time")
    name = data.get("name")
    phone = data.get("phone")
    email = data.get("email")

    if not all([date, time_slot, name, phone, email]):
        return jsonify({"error": "Dati incompleti"}), 400

    # Controllo periodo prenotazioni
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    start_period = datetime(2026, 4, 1)
    end_period = datetime(2026, 7, 31)
    if not (start_period <= date_obj <= end_period):
        return jsonify({"error": "Prenotazioni disponibili solo dal 1 Aprile 2026 al 31 Luglio 2026"}), 400

    now = int(time.time())
    ten_minutes = 10 * 60

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT id FROM bookings
        WHERE date=? AND time=? AND (paid=1 OR (reserved_until IS NOT NULL AND reserved_until > ?))
    """, (date, time_slot, now))
    if cur.fetchone():
        db.close()
        return jsonify({"error": "Slot già prenotato o riservato"}), 400

    reserved_until = now + ten_minutes
    cur.execute("""
        INSERT INTO bookings(date, time, name, phone, email, reserved_until)
        VALUES (?,?,?,?,?,?)
    """, (date, time_slot, name, phone, email, reserved_until))
    booking_id = cur.lastrowid
    db.commit()
    db.close()

    return jsonify({"booking_id": booking_id})

# --------------------------
# Slot disponibili dinamici
# --------------------------
@app.route("/slots", methods=["GET"])
def get_slots():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify([])

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")

    # Controllo periodo prenotazioni
    start_period = datetime(2026, 4, 1)
    end_period = datetime(2026, 7, 31)
    if not (start_period <= date_obj <= end_period):
        return jsonify([])

    # Determina il giorno della settimana
    weekday = date_obj.weekday()  # 0=Lun, 6=Dom

    # Crea lista slot dinamica
    all_slots = []
    if weekday <= 4:  # Lun-Ven
        start = datetime.combine(date_obj, datetime.strptime("17:30", "%H:%M").time())
        end = datetime.combine(date_obj, datetime.strptime("20:30", "%H:%M").time())
    else:  # Sab-Dom
        start = datetime.combine(date_obj, datetime.strptime("09:00", "%H:%M").time())
        end = datetime.combine(date_obj, datetime.strptime("17:00", "%H:%M").time())

    current = start
    while current < end:
        all_slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=60)

    # Pulisce slot temporaneamente riservati scaduti
    now = int(time.time())
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE bookings SET reserved_until=NULL WHERE reserved_until IS NOT NULL AND reserved_until<? AND paid=0", (now,))
    db.commit()

    cur.execute("SELECT time, paid, reserved_until FROM bookings WHERE date=?", (date_str,))
    booked_rows = cur.fetchall()
    db.close()

    booked = [row[0] for row in booked_rows if row[1]==1 or (row[2] is not None and row[2]>now)]
    available = [s for s in all_slots if s not in booked]

    return jsonify(available)

# --------------------------
# Webhook simulato pagamento
# --------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    booking_id = data.get("booking_id")
    if booking_id:
        db = get_db()
        cur = db.cursor()
        cur.execute("UPDATE bookings SET paid=1, reserved_until=NULL WHERE id=?", (booking_id,))
        db.commit()
        cur.execute("SELECT email,date,time FROM bookings WHERE id=?", (booking_id,))
        row = cur.fetchone()
        if row:
            email, date, time_slot = row
            send_email(email, date, time_slot)
        db.close()
    return "", 200

# --------------------------
# Cancellazione prenotazione admin
# --------------------------
@app.route("/delete_booking", methods=["POST"])
def delete_booking():
    data = request.json
    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"error": "ID prenotazione mancante"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    db.commit()
    db.close()
    return jsonify({"success": True})

# --------------------------
# Funzione invio email
# --------------------------
def send_email(to_email, date, time_slot):
    from_email = "tuatuaemail@gmail.com"
    password = "LA_TUA_PASSWORD_APP"
    subject = "Conferma Prenotazione Campo Tennis"
    body = f"Prenotazione confermata per il {date} alle ore {time_slot}."
    message = f"Subject: {subject}\n\n{body}"

    try:
        s = smtplib.SMTP("smtp.gmail.com", 587)
        s.starttls()
        s.login(from_email, password)
        s.sendmail(from_email, to_email, message)
        s.quit()
    except Exception as e:
        print("Errore invio email:", e)

# --------------------------
# Main
# --------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
