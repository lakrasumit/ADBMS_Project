-- Run individual SELECTs in Neon SQL Editor; substitute the fictional values.
-- Ordered route search and live availability.
SELECT t.train_number, r.service_date, o.departure_time, d.arrival_time,
 (SELECT count(*) FROM seat s WHERE s.run_id=r.run_id AND NOT EXISTS
  (SELECT 1 FROM booking b WHERE b.seat_id=s.seat_id AND b.status='CONFIRMED')) AS available
FROM train t JOIN train_run r USING(train_id)
JOIN train_stop o ON o.train_id=t.train_id JOIN station os ON os.station_id=o.station_id
JOIN train_stop d ON d.train_id=t.train_id JOIN station ds ON ds.station_id=d.station_id
WHERE trim(os.station_code)='MAPLE' AND trim(ds.station_code)='PINE'
AND o.stop_sequence<d.stop_sequence AND r.service_date=CURRENT_DATE;

-- Booking history, including cancellations.
SELECT p.full_name,b.pnr,b.status,b.fare_inr,b.booked_at,r.service_date,t.train_number
FROM passenger p JOIN booking b USING(passenger_id) JOIN seat s USING(seat_id)
JOIN train_run r USING(run_id) JOIN train t USING(train_id)
WHERE p.email='traveller@example.test' ORDER BY b.booked_at DESC;

-- Counts include empty runs; count FILTER avoids counting empty outer-join rows.
SELECT r.run_id,t.train_number,r.service_date,
 count(b.booking_id) FILTER(WHERE b.status='CONFIRMED') AS confirmed,
 count(b.booking_id) FILTER(WHERE b.status='CANCELLED') AS cancelled
FROM train_run r JOIN train t USING(train_id) LEFT JOIN seat s USING(run_id)
LEFT JOIN booking b USING(seat_id) GROUP BY r.run_id,t.train_number,r.service_date
ORDER BY r.service_date,t.train_number;

-- Integrity audit: must return zero rows.
SELECT seat_id,count(*) FROM booking WHERE status='CONFIRMED'
GROUP BY seat_id HAVING count(*)>1;
