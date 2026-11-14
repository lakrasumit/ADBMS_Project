-- Additive initialization only. Existing rows are never reset.
CREATE TABLE IF NOT EXISTS passenger (
 passenger_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 full_name VARCHAR(120) NOT NULL CHECK (length(trim(full_name)) > 0),
 email VARCHAR(254) NOT NULL UNIQUE CHECK (length(trim(email)) > 0)
);
CREATE TABLE IF NOT EXISTS train (
 train_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 train_number VARCHAR(10) NOT NULL UNIQUE CHECK (length(trim(train_number)) > 0),
 train_name VARCHAR(120) NOT NULL CHECK (length(trim(train_name)) > 0)
);
CREATE TABLE IF NOT EXISTS station (
 station_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 station_code CHAR(5) NOT NULL UNIQUE CHECK (trim(station_code) ~ '^[A-Z0-9]{1,5}$'),
 station_name VARCHAR(120) NOT NULL CHECK (length(trim(station_name)) > 0)
);
CREATE TABLE IF NOT EXISTS train_stop (
 train_id BIGINT NOT NULL REFERENCES train ON DELETE RESTRICT,
 stop_sequence SMALLINT NOT NULL CHECK (stop_sequence > 0),
 station_id BIGINT NOT NULL REFERENCES station ON DELETE RESTRICT,
 arrival_time TIME, departure_time TIME,
 PRIMARY KEY (train_id, stop_sequence), UNIQUE (train_id, station_id),
 CHECK (arrival_time IS NOT NULL OR departure_time IS NOT NULL),
 CHECK (arrival_time IS NULL OR departure_time IS NULL OR arrival_time <= departure_time)
);
CREATE TABLE IF NOT EXISTS train_run (
 run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 train_id BIGINT NOT NULL REFERENCES train ON DELETE RESTRICT,
 service_date DATE NOT NULL, UNIQUE (train_id, service_date)
);
CREATE TABLE IF NOT EXISTS seat (
 seat_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 run_id BIGINT NOT NULL REFERENCES train_run ON DELETE RESTRICT,
 coach_code VARCHAR(6) NOT NULL CHECK (length(trim(coach_code)) > 0),
 seat_number VARCHAR(6) NOT NULL CHECK (length(trim(seat_number)) > 0),
 UNIQUE (run_id, coach_code, seat_number)
);
CREATE TABLE IF NOT EXISTS booking (
 booking_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 pnr CHAR(10) NOT NULL UNIQUE CHECK (pnr ~ '^[A-Z0-9]{10}$'),
 passenger_id BIGINT NOT NULL REFERENCES passenger ON DELETE RESTRICT,
 seat_id BIGINT NOT NULL REFERENCES seat ON DELETE RESTRICT,
 fare_inr NUMERIC(9,2) NOT NULL CHECK (fare_inr >= 0),
 status VARCHAR(12) NOT NULL CHECK (status IN ('CONFIRMED','CANCELLED')),
 booked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS one_confirmed_booking_per_seat
 ON booking(seat_id) WHERE status = 'CONFIRMED';
CREATE INDEX IF NOT EXISTS booking_by_passenger_time ON booking(passenger_id, booked_at DESC);
CREATE INDEX IF NOT EXISTS train_stop_by_station ON train_stop(station_id, train_id, stop_sequence);
CREATE INDEX IF NOT EXISTS train_run_by_date ON train_run(service_date, train_id);
-- Additive Clerk integration: old history stays intact and unclaimed.
ALTER TABLE booking ADD COLUMN IF NOT EXISTS clerk_user_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS booking_by_clerk_user ON booking(clerk_user_id, booked_at DESC);
