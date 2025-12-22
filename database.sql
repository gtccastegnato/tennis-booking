CREATE TABLE bookings (
id INTEGER PRIMARY KEY AUTOINCREMENT,
date TEXT,
time TEXT,
name TEXT,
phone TEXT,
email TEXT,
paid INTEGER DEFAULT 0,
created_at DATETIME,
expires_at DATETIME,
stripe_session TEXT
);