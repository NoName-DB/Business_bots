-- add slot_interval_minutes to master_schedule
PRAGMA foreign_keys = ON;

ALTER TABLE master_schedule 
ADD slot_interval_minutes INTEGER;