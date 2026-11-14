# Railway Reservation System

Student-scale Flask / PostgreSQL application implementing `../DBMS_Project_Report.md`
and `../diagrams/railway-erd.mmd`. Existing report and diagram assets are untouched.

## Setup (PowerShell)

From this folder:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# Only on first setup; do not overwrite an existing .env.
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

In [Neon Console](https://console.neon.tech), create a project/database for this
classroom demo. Click **Connect**, choose the branch, database and role, then copy
the PostgreSQL connection string into `DATABASE_URL` in `.env`. Retain
`sslmode=require` and any supplied `channel_binding=require`. Never paste the
connection string into source files, screenshots, terminal commands or commits.
Both pooled and direct URLs work; direct is easiest for SQL Editor demonstrations.
Use a dedicated empty database so similarly named unrelated tables cannot collide.
The application enforces SSL even if the URL requests an insecure mode; stronger
`verify-ca` / `verify-full` settings are retained. Connection errors are sanitized.

Optionally set `SECRET_KEY` to a long random string for stable sessions and
`CLERK_KEY` to a shared classroom schedule key. Restart after changing `.env`.
`.env` is ignored by the included `.gitignore`; `.env.example` has placeholders only.

### Clerk authentication

This Flask app uses the existing **Railway** Clerk application
`app_3LXtGXsjDtJlgw7aB7acJVCF9ul`. Flask is not a Clerk CLI scaffolding target;
the integration uses ClerkJS 6 / UI 1 script components and the official
`clerk-backend-api` Python SDK. Do not scaffold a replacement Next.js app.
Clerk's skills are already installed on this machine.

From this folder, if connecting a fresh checkout:

```powershell
npx -y clerk@latest auth login
npx -y clerk@latest link --app app_3LXtGXsjDtJlgw7aB7acJVCF9ul
npx -y clerk@latest env pull --app app_3LXtGXsjDtJlgw7aB7acJVCF9ul --instance dev --file .env.clerk
```

`.env.clerk` is CLI-managed and ignored, and is loaded automatically by `auth.py`.
Keep Neon and Flask settings in `.env`; existing environment variables take precedence.
Only `CLERK_PUBLISHABLE_KEY` is sent to the browser. Never paste or print
`CLERK_SECRET_KEY`. Both files must remain private. Clerk CLI `doctor` may warn
that the main `.env` lacks Clerk keys: this app deliberately loads `.env.clerk`
separately. The initial host diagnostic also warned that the CLI could be updated
and that no production instance exists; production is outside this project scope.
The final check used `npx -y clerk@latest doctor --json` (4.1.0), which passed
authentication, application reachability and project linking; the CLI-version
warning was resolved by using the latest runner.

Search and run details are public. Booking, PNR lookup/cancellation and schedule
management require a verified Clerk session. The existing optional `CLERK_KEY`
is a **classroom schedule access key**, unrelated to Clerk's API keys. It remains
an additional schedule gate and its unlock is scoped to the signed-in account.
Without that key, any signed-in user can edit the classroom schedule; no admin
role system has been added.

Use `http://localhost:5000` or `http://127.0.0.1:5000` consistently. These are the
default allowed token origins. If you choose another port, put its complete origin
in the comma-separated `CLERK_AUTHORIZED_PARTIES` setting in `.env` and restart.
The current verified preview uses **http://127.0.0.1:5050/sign-in**, leaving an older
service on port 5000 untouched; its process has both 5000 and 5050 origins allowed.
To start the preview port again:

```powershell
$env:CLERK_AUTHORIZED_PARTIES='http://localhost:5050,http://127.0.0.1:5050'
python -m flask --app app run --host 127.0.0.1 --port 5050
```

Open Sign up to create your own development user, or Sign in to use an existing
user. Current provider choices come from your existing Clerk application and have
not been changed. ClerkJS loads from the instance CDN, so authentication requires
internet access and JavaScript. Python verifies signature, expiry, allowed origin
and issuer on protected requests; decoding a token alone never grants access.

```powershell
python -m flask --app app init-db --seed
python -m flask --app app run --host 127.0.0.1 --port 5000
```

Open [the local application](http://127.0.0.1:5000). Do not enable debug mode for a
shared demo. Initialization creates missing tables/indexes and inserts fictional
data using `ON CONFLICT DO NOTHING`; it never drops tables, resets sequences or
overwrites existing records. Reruns add missing sample runs for today through 14
days ahead (a 15-day schedule window). The demo includes seven stations and six
fictional trains. Initialization also adds the nullable `booking.clerk_user_id`
column and its history index if missing. Other existing schema differences are not
migrated or repaired. All initialization is transactional. To initialize without
samples, omit `--seed`.

## Demonstration

1. Search Maple Junction to Pine Central on today's date; Woodland Express appears.
   Reverse the stations to see Valley Local. Same-station search is rejected.
2. Sign in, then view the full route and select one available C1 seat. Enter fictional name
   `Demo Traveller` and email `traveller@example.test`. Confirm the ₹250 booking.
3. Save the generated 10-character PNR and use PNR lookup in the same account. Cancel with the
   confirmation checkbox, then book that seat again. Both historical rows remain.
4. In Manage schedule add stations, train, increasing stop sequences/times, a dated
   run, then seats for that run. Edit links populate the same forms. Record IDs in
   the tables correspond to the named dropdown choices. No delete/reset UI exists.
5. Run the read-only statements in `demo_queries.sql` in Neon SQL Editor for joins,
   passenger history, filtered aggregates, and the active-seat integrity audit.

## Database design and assumptions

Seven entities follow the report exactly: passenger, train, station, train_stop,
train_run, seat and booking. A seat belongs to one run; booking reaches the run
through its seat, avoiding a redundant run foreign key. A unique partial index
on `booking(seat_id) WHERE status='CONFIRMED'` permits many cancelled historical
rows but only one current owner. Identity keys, composite stop keys, foreign keys,
unique business keys, required fields and CHECK constraints illustrate integrity.

`services.book` locks the seat with `SELECT ... FOR UPDATE`, then checks active
ownership and inserts within the same psycopg connection transaction. Under the
default READ COMMITTED isolation, a waiting contender sees the committed booking
on its subsequent check. The index is an independent final guard. Exceptions roll
back passenger and booking writes together; PNR collisions retry with a new random
PNR. Cancellation takes the seat lock first and changes status only.

Small additions to the report's assumptions:

- Fixed ₹250 full-run demo fare, supplied by the server and snapshotted in booking.
- Same-day ordered schedules only, in Asia/Kolkata operating time. Service date is
  the run's start date. Overnight offsets, diversions and departure cutoffs are omitted;
  past dated runs remain bookable for repeatable classroom demonstrations.
- Emails are normalized to lowercase. Reusing an email requires the same name;
  passenger details are not overwritten by another booking.
- Clerk authentication was added at the user's subsequent request. New bookings
  store the authenticated external user ID in `booking.clerk_user_id`; PNR lookup
  and cancellation filter by that ID in SQL. Passengers remain separate from the
  account placing a reservation. The seven report entities remain unchanged;
  this is one additional booking attribute, not a local password/user table.
  Historical bookings predating Clerk remain intact with a null owner and cannot
  be viewed/cancelled through the account UI. They are not automatically claimed
  by matching an email or PNR. Any future reassignment needs a separately reviewed
  administrative process. No old rows were reassigned during setup.
- Stop times must increase with sequence, at least one time is required per stop,
  and duplicate stations are disallowed. Route completeness (two or more stops)
  is the clerk's responsibility. No segment allocation or journey endpoints are
  stored in bookings; lookup shows the full run.
- Existing run/seat/stop edits with booking history are rejected to reduce historical
  ambiguity. Master names and newly added stops are shared current schedule data,
  not immutable historical timetable snapshots. Keep schedule editing separate
  from the concurrency booking demo.

No payments, refunds, waitlist, operator API, tracking, deployment or complex roles.
The web forms use session CSRF tokens, server validation and escaped templates.
SQL values use psycopg parameters; schedule identifiers come from a static allowlist
and `psycopg.sql.Identifier`. No user text is interpolated into SQL.

## Verification

Offline checks:

```powershell
python -m compileall -q app.py auth.py db.py services.py
python -m unittest discover -s tests -v
```

Offline tests use mocked database boundaries, not PostgreSQL substitutes. They do
not establish that PostgreSQL constraints, row locks or Neon connectivity work.

After configuring Neon, perform these manual database checks:

1. Run initialization twice; verify no duplicate sample seats, trains or runs.
2. Complete the booking/cancel/rebook workflow and inspect all history rows.
3. Open the same seat selection in two independent browser sessions. Submit both
   together: exactly one confirms and the other reports unavailable. Run the audit
   SELECT in `demo_queries.sql`; it must return no rows.
4. Repeat cancellation: it must report already cancelled without another update.
5. Try duplicate station codes, stop sequence/station, run date, and coach/seat;
   invalid order and unknown IDs should fail with friendly messages.
6. In a disposable test transaction in SQL Editor, attempt invalid foreign keys,
   duplicate PNR, negative fare, invalid booking status and a second confirmed
   booking for a reserved seat. Each must fail; use ROLLBACK, never reset/drop data.
7. Disconnect networking to verify the friendly database-unavailable response.
8. Sign out and confirm lookup/schedule redirect to sign-in; sign in as another
   account and confirm that the first account's PNR cannot be viewed or cancelled.
   Confirm the user menu signs out and repeat access checks. Keep the two-user
   contention test separate from schedule editing.

References: [Neon connection instructions](https://neon.com/docs/connect/connect-from-any-app)
and [psycopg 3 transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

## Recorded checks in this workspace

The earlier dependency/network blocker was resolved during Clerk setup. The project
virtual environment now contains the required packages. All 16 unit tests passed,
including real SDK JWT verification using synthetic RSA keys, rejecting expired,
wrong-origin, wrong-issuer and forged tokens, anonymous route checks and SQL owner
filters. Python compilation and JavaScript syntax checks passed. Tests do not create
Clerk users or contact external services.

The selected existing Clerk app was linked and its development keys pulled through
the authenticated host CLI. Neon additive initialization succeeded with existing
data retained. The local server was started on port 5050, and the browser rendered
the real Railway sign-in form. No real account was created or signed in by the
assistant. Full sign-in/sign-out, signed-in booking/cancellation, live two-user
isolation and database concurrency still need the manual workflow above.
Final read-only checks confirmed HTTP 200 for home/sign-in, redirects for anonymous
lookup/schedule access, and the ownership column/index present in Neon. All eight
templates compiled, and `pip check` reported no broken requirements.

Implementation references: [Clerk JavaScript quickstart](https://clerk.com/docs/js-frontend/getting-started/quickstart)
and [official Python SDK request authentication](https://github.com/clerk/clerk-sdk-python#request-authentication).
