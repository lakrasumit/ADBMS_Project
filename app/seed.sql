-- Fictional services and stations; safe to rerun without overwriting edits.
INSERT INTO station(station_code, station_name) VALUES
 ('MAPLE','Maple Junction'), ('CEDAR','Cedar Town'), ('PINE','Pine Central'),
 ('HILL','Hillview'), ('RIVER','Riverbend'), ('LAKE','Lakeside'), ('MEADO','Meadow Park')
 ON CONFLICT DO NOTHING;

INSERT INTO train(train_number, train_name) VALUES
 ('D101','Woodland Express'), ('D102','Valley Local'),
 ('D103','Mountain Link'), ('D104','Riverside Express'),
 ('D105','Lake & Meadow Local'), ('D106','Highland Connector')
 ON CONFLICT DO NOTHING;

INSERT INTO train_stop(train_id, stop_sequence, station_id, arrival_time, departure_time)
 SELECT t.train_id, v.seq, s.station_id, v.arr::time, v.dep::time
 FROM (VALUES
 ('D101',1,'MAPLE',NULL,'08:00'), ('D101',2,'CEDAR','09:00','09:05'),
 ('D101',3,'PINE','10:30',NULL),
 ('D102',1,'PINE',NULL,'14:00'), ('D102',2,'CEDAR','15:00','15:05'),
 ('D102',3,'MAPLE','16:30',NULL),
 ('D103',1,'MAPLE',NULL,'06:30'), ('D103',2,'CEDAR','07:25','07:30'),
 ('D103',3,'HILL','08:20','08:25'), ('D103',4,'PINE','09:30',NULL),
 ('D104',1,'PINE',NULL,'06:45'), ('D104',2,'LAKE','07:35','07:40'),
 ('D104',3,'RIVER','08:30','08:35'), ('D104',4,'CEDAR','09:20','09:25'),
 ('D104',5,'MAPLE','10:10',NULL),
 ('D105',1,'MAPLE',NULL,'11:10'), ('D105',2,'LAKE','11:55','12:00'),
 ('D105',3,'MEADO','12:40','12:45'), ('D105',4,'CEDAR','13:25','13:30'),
 ('D105',5,'PINE','14:20',NULL),
 ('D106',1,'HILL',NULL,'14:00'), ('D106',2,'MEADO','14:50','14:55'),
 ('D106',3,'CEDAR','15:40','15:45'), ('D106',4,'MAPLE','16:30',NULL)
 ) v(num,seq,code,arr,dep)
 JOIN train t ON t.train_number=v.num
 JOIN station s ON trim(s.station_code)=v.code
 ON CONFLICT DO NOTHING;

-- Today through 14 days ahead, giving the classroom demo a 15-day horizon.
INSERT INTO train_run(train_id, service_date)
 SELECT train_id, CURRENT_DATE + offset_day FROM train
 CROSS JOIN generate_series(0,14) AS offset_day
 WHERE train_number IN ('D101','D102','D103','D104','D105','D106')
 ON CONFLICT DO NOTHING;

INSERT INTO seat(run_id, coach_code, seat_number)
 SELECT r.run_id, 'C1', n::text FROM train_run r JOIN train t USING(train_id)
 CROSS JOIN generate_series(1,8) AS n
 WHERE t.train_number IN ('D101','D102','D103','D104','D105','D106')
 ON CONFLICT DO NOTHING;
