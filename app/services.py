"""Parameterized queries and the reservation transaction."""
import secrets
import string
from decimal import Decimal
from db import connect
from psycopg.errors import UniqueViolation

FARE = Decimal('250.00')

class UserError(Exception):
    pass

def rows(query, params=()):
    with connect() as conn:
        return conn.execute(query, params).fetchall()

def search_runs(origin, destination, day):
    if origin == destination:
        raise UserError('Choose two different stations in travel order.')
    return rows('''SELECT r.run_id, r.service_date, t.train_number, t.train_name,
        o.departure_time, d.arrival_time,
        (SELECT count(*) FROM seat s WHERE s.run_id=r.run_id AND NOT EXISTS
          (SELECT 1 FROM booking b WHERE b.seat_id=s.seat_id AND b.status='CONFIRMED')) AS available
        FROM train_run r JOIN train t USING(train_id)
        JOIN train_stop o ON o.train_id=t.train_id
        JOIN train_stop d ON d.train_id=t.train_id
        WHERE o.station_id=%s AND d.station_id=%s AND o.stop_sequence<d.stop_sequence
        AND r.service_date=%s ORDER BY o.departure_time, t.train_number''', (origin, destination, day))

def book(seat_id, name, email, owner_id):
    if not owner_id:
        raise UserError('Sign in before booking a seat.')
    # PNR collisions retry in a fresh transaction; seat conflicts never retry blindly.
    for _ in range(3):
        try:
            with connect() as conn:
                seat = conn.execute('SELECT seat_id FROM seat WHERE seat_id=%s FOR UPDATE', (seat_id,)).fetchone()
                if not seat:
                    raise UserError('That seat no longer exists. Choose a scheduled run again.')
                active = conn.execute("SELECT booking_id FROM booking WHERE seat_id=%s AND status='CONFIRMED'", (seat_id,)).fetchone()
                if active:
                    raise UserError('That seat was just reserved. Please choose another seat.')
                passenger = conn.execute('''INSERT INTO passenger(full_name,email) VALUES (%s,%s)
                    ON CONFLICT (email) DO UPDATE SET email=EXCLUDED.email RETURNING passenger_id,full_name''', (name,email)).fetchone()
                if passenger['full_name'] != name:
                    raise UserError('That email already belongs to a different passenger name. Use the original name.')
                pnr = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))
                conn.execute('''INSERT INTO booking(pnr,passenger_id,seat_id,fare_inr,status,clerk_user_id)
                    VALUES (%s,%s,%s,%s,'CONFIRMED',%s)''', (pnr,passenger['passenger_id'],seat_id,FARE,owner_id))
            return pnr
        except UniqueViolation as exc:
            if exc.diag.constraint_name != 'booking_pnr_key':
                raise UserError('That seat was just reserved. Please choose another seat.') from None
    raise UserError('Could not generate a PNR. Please try again.')

def booking(pnr, owner_id):
    result = rows('''SELECT b.*, p.full_name, p.email, s.coach_code, s.seat_number,
      r.run_id, r.service_date, t.train_number, t.train_name FROM booking b
      JOIN passenger p USING(passenger_id) JOIN seat s USING(seat_id)
      JOIN train_run r USING(run_id) JOIN train t USING(train_id)
      WHERE b.pnr=%s AND b.clerk_user_id=%s''', (pnr,owner_id))
    if not result:
        raise UserError('No booking in your account matches that PNR. Check all 10 characters.')
    return result[0]

def cancel(pnr, owner_id):
    with connect() as conn:
        # Same seat-first lock order as booking; history is never deleted.
        seat = conn.execute('''SELECT s.seat_id FROM seat s JOIN booking b USING(seat_id)
          WHERE b.pnr=%s AND b.clerk_user_id=%s FOR UPDATE OF s''', (pnr,owner_id)).fetchone()
        if not seat:
            raise UserError('No booking in your account matches that PNR.')
        changed = conn.execute("UPDATE booking SET status='CANCELLED' WHERE pnr=%s AND clerk_user_id=%s AND status='CONFIRMED' RETURNING booking_id", (pnr,owner_id)).fetchone()
        if not changed:
            raise UserError('This booking is already cancelled. Its history is retained.')
