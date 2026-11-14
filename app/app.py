import hmac
import os
import re
import secrets
from datetime import date, time
from pathlib import Path
import click
import psycopg
from flask import Flask, render_template, request, redirect, url_for, flash, session
from db import connect, ConfigurationError
from services import rows, search_runs, book, booking, cancel, UserError, FARE
from auth import current_user_id, login_required, public_config, safe_next

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=32768)

@app.context_processor
def context():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_hex(24)
    # Keep error pages renderable even when auth configuration is incomplete.
    try:
        clerk = public_config()
    except ConfigurationError:
        clerk = {'key': '', 'domain': ''}
    return dict(csrf=session['csrf'], fare=FARE, clerk=clerk)

@app.get('/sign-in')
def sign_in():
    return render_template('auth.html', mode='sign-in', next_path=safe_next(request.args.get('next')))

@app.get('/sign-up')
def sign_up():
    return render_template('auth.html', mode='sign-up', next_path=safe_next(request.args.get('next')))

@app.before_request
def csrf_check():
    if request.method == 'POST' and not hmac.compare_digest(session.get('csrf', ''), request.form.get('csrf', '')):
        return render_template('error.html', message='This form expired. Reload the page and try again.'), 400

@app.errorhandler(UserError)
def user_error(exc):
    return render_template('error.html', message=str(exc)), 400

@app.errorhandler(ConfigurationError)
def configuration_error(exc):
    return render_template('error.html', message=str(exc)), 503

@app.errorhandler(psycopg.Error)
def database_error(exc):
    if isinstance(exc, psycopg.IntegrityError):
        message = 'The change conflicts with an existing record or a database rule. Check unique codes, dates and references.'
        code = 409
    else:
        message = 'The database is unavailable or not initialized. Check your Neon connection and run init-db, then retry.'
        code = 503
    # Never expose or log connection exceptions: they can contain connection details.
    return render_template('error.html', message=message), code

def text_field(name, maximum):
    value = request.form.get(name, '').strip()
    if not value or len(value) > maximum:
        raise UserError(f'{name.replace("_", " ").capitalize()} is required (maximum {maximum} characters).')
    return value

def number(value):
    try:
        result = int(value)
        if result <= 0 or result > 9223372036854775807:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise UserError('Choose a valid record or positive sequence number.') from None

def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise UserError('Choose a valid service date.') from None

@app.get('/')
def index():
    stations = rows('SELECT * FROM station ORDER BY station_name')
    matches = None
    if request.args.get('date'):
        origin = number(request.args.get('origin'))
        destination = number(request.args.get('destination'))
        valid = {s['station_id'] for s in stations}
        if origin not in valid or destination not in valid:
            raise UserError('Choose existing origin and destination stations.')
        matches = search_runs(origin, destination, parse_date(request.args['date']))
    return render_template('search.html', stations=stations, matches=matches, today=date.today().isoformat())

@app.get('/runs/<int:run_id>')
def run(run_id):
    found = rows('SELECT * FROM train_run JOIN train USING(train_id) WHERE run_id=%s', (run_id,))
    if not found:
        raise UserError('That train run does not exist.')
    seats = rows('''SELECT s.*, NOT EXISTS(SELECT 1 FROM booking b WHERE b.seat_id=s.seat_id
       AND b.status='CONFIRMED') AS available FROM seat s WHERE run_id=%s ORDER BY coach_code,seat_id''', (run_id,))
    stops = rows('SELECT * FROM train_stop JOIN station USING(station_id) WHERE train_id=%s ORDER BY stop_sequence', (found[0]['train_id'],))
    return render_template('run.html', run=found[0], seats=seats, stops=stops)

@app.post('/book')
@login_required
def reserve():
    name = text_field('full_name', 120)
    email = text_field('email', 254).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise UserError('Enter a valid email address, such as traveller@example.test.')
    pnr = book(number(request.form.get('seat_id')), name, email, current_user_id())
    flash('Seat confirmed. Save your PNR to view or cancel this booking.')
    return redirect(url_for('lookup', pnr=pnr))

def pnr_value(value):
    value = value.strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{10}', value):
        raise UserError('A PNR contains exactly 10 letters and digits.')
    return value

@app.get('/booking')
@login_required
def lookup():
    record = booking(pnr_value(request.args['pnr']), current_user_id()) if request.args.get('pnr') else None
    return render_template('booking.html', booking=record)

@app.post('/cancel')
@login_required
def cancellation():
    pnr = pnr_value(request.form.get('pnr', ''))
    if request.form.get('confirm') != 'yes':
        raise UserError('Tick the confirmation box to cancel this booking.')
    cancel(pnr, current_user_id())
    flash('Booking cancelled. The seat is available again; the booking history remains.')
    return redirect(url_for('lookup', pnr=pnr))

# Static allowlist: SQL identifiers never come from browser input.
MODELS = {
 'train': ('train_id', [('train_number','Train number'),('train_name','Train name')]),
 'station': ('station_id', [('station_code','Station code'),('station_name','Station name')]),
 'train_stop': ('stop_sequence', [('train_id','Train'),('stop_sequence','Sequence'),('station_id','Station'),('arrival_time','Arrival'),('departure_time','Departure')]),
 'train_run': ('run_id', [('train_id','Train'),('service_date','Service date')]),
 'seat': ('seat_id', [('run_id','Dated run'),('coach_code','Coach'),('seat_number','Seat number')])
}

@app.route('/schedule', methods=['GET','POST'])
@login_required
def schedule():
    key = os.getenv('CLERK_KEY', '')
    if key and session.get('schedule_clerk_user') != current_user_id():
        if request.method == 'POST' and hmac.compare_digest(request.form.get('clerk_key', ''), key):
            session['schedule_clerk_user'] = current_user_id()
            return redirect(url_for('schedule'))
        return render_template('clerk.html', failed=request.method == 'POST')
    kind = request.args.get('kind', 'train')
    if kind not in MODELS:
        raise UserError('Choose a valid schedule section.')
    pk, fields = MODELS[kind]
    original = request.args.get('edit', '')
    parent = request.args.get('parent', '')
    from psycopg import sql
    table = sql.Identifier(kind)
    where = sql.SQL('{}=%s').format(sql.Identifier(pk))
    identity = [number(original)] if original else []
    if kind == 'train_stop' and original:
        where += sql.SQL(' AND train_id=%s')
        identity.append(number(parent))
    with connect() as conn:
        if request.method == 'POST':
            values = []
            for field, _ in fields:
                raw = request.form.get(field, '').strip()
                if field.endswith('_id') or field == 'stop_sequence':
                    value = number(raw)
                    if field == 'stop_sequence' and value > 32767:
                        raise UserError('Sequence must be between 1 and 32767.')
                elif field == 'service_date':
                    value = parse_date(raw)
                elif field.endswith('_time'):
                    try:
                        value = time.fromisoformat(raw) if raw else None
                    except ValueError:
                        raise UserError('Use a valid 24-hour schedule time.') from None
                else:
                    maximum = 120 if field.endswith('_name') else {'station_code':5,'train_number':10}.get(field,6)
                    value = text_field(field, maximum)
                    if field in ('station_code','coach_code'):
                        value = value.upper()
                values.append(value)
            if kind == 'train_stop':
                tid, seq, sid, arrival, departure = values
                if not (arrival or departure) or (arrival and departure and arrival > departure):
                    raise UserError('Provide a time; departure must be at or after arrival.')
                # Serialize edits of this route, and check the complete proposed order.
                conn.execute('SELECT train_id FROM train WHERE train_id=%s FOR UPDATE', (tid,))
                proposed = conn.execute('SELECT * FROM train_stop WHERE train_id=%s ORDER BY stop_sequence', (tid,)).fetchall()
                proposed = [s for s in proposed if not (original and s['train_id']==number(parent) and s['stop_sequence']==number(original))]
                proposed.append(dict(stop_sequence=seq,arrival_time=arrival,departure_time=departure))
                previous = None
                for stop in sorted(proposed, key=lambda s:s['stop_sequence']):
                    start = stop['arrival_time'] or stop['departure_time']
                    if previous and start < previous:
                        raise UserError('Stop times must increase with sequence. Overnight routes are outside this demo.')
                    previous = stop['departure_time'] or stop['arrival_time']
            # Preserve historical schedule references once this train/run has any booking.
            if original and kind in ('train_stop','train_run','seat'):
                if kind == 'train_stop':
                    locked = conn.execute('SELECT train_id FROM train WHERE train_id=%s FOR UPDATE', (number(parent),)).fetchone()
                    used = conn.execute('SELECT 1 FROM booking JOIN seat USING(seat_id) JOIN train_run USING(run_id) WHERE train_id=%s LIMIT 1', (number(parent),)).fetchone()
                elif kind == 'train_run':
                    conn.execute('SELECT seat_id FROM seat WHERE run_id=%s ORDER BY seat_id FOR UPDATE', (number(original),)).fetchall()
                    used = conn.execute('SELECT 1 FROM booking JOIN seat USING(seat_id) WHERE run_id=%s LIMIT 1', (number(original),)).fetchone()
                else:
                    conn.execute('SELECT seat_id FROM seat WHERE seat_id=%s FOR UPDATE', (number(original),)).fetchone()
                    used = conn.execute('SELECT 1 FROM booking WHERE seat_id=%s LIMIT 1', (number(original),)).fetchone()
                if used:
                    raise UserError('This schedule has booking history. Add a new run/train instead of changing its journey or inventory.')
            columns = sql.SQL(',').join(sql.Identifier(f) for f,_ in fields)
            if original:
                assignments = sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(f)) for f,_ in fields)
                result = conn.execute(sql.SQL('UPDATE {} SET {} WHERE {} RETURNING *').format(table,assignments,where), values+identity).fetchone()
                if not result:
                    raise UserError('The record you tried to edit no longer exists.')
            else:
                conn.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(table,columns,sql.SQL(',').join(sql.Placeholder() for _ in values)), values)
            flash('Schedule saved.')
            return redirect(url_for('schedule', kind=kind))
        records = conn.execute(sql.SQL('SELECT * FROM {} ORDER BY {}').format(table,sql.Identifier(pk))).fetchall()
        edit = conn.execute(sql.SQL('SELECT * FROM {} WHERE {}').format(table,where), identity).fetchone() if original else None
        if original and not edit:
            raise UserError('That schedule record does not exist.')
        choices = {
          'train_id': conn.execute('SELECT train_id AS id, train_number || \' / \' || train_name AS label FROM train ORDER BY train_number').fetchall(),
          'station_id': conn.execute('SELECT station_id AS id, station_name AS label FROM station ORDER BY station_name').fetchall(),
          'run_id': conn.execute('SELECT run_id AS id, train_number || \' / \' || service_date::text AS label FROM train_run JOIN train USING(train_id) ORDER BY service_date DESC').fetchall()}
    return render_template('schedule.html', kind=kind, models=MODELS, fields=fields, records=records, edit=edit, pk=pk, choices=choices, protected=bool(key))

@app.cli.command('init-db')
@click.option('--seed', is_flag=True, help='Also insert fictional demo schedules.')
def init_db(seed):
    try:
        with connect() as conn:
            conn.execute("SET LOCAL TIME ZONE 'Asia/Kolkata'")
            conn.execute(Path(__file__).with_name('schema.sql').read_text(), prepare=False)
            if seed:
                conn.execute(Path(__file__).with_name('seed.sql').read_text(), prepare=False)
    except (ConfigurationError, psycopg.Error):
        raise click.ClickException('Initialization failed. Check DATABASE_URL and database permissions. No connection details are displayed.') from None
    click.echo('Schema ready. Existing data retained.' + (' Fictional sample data added.' if seed else ''))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
