-- Add reminder flags to bookings
PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

ALTER TABLE bookings ADD COLUMN reminded_24 INTEGER DEFAULT 0;
ALTER TABLE bookings ADD COLUMN reminded_1 INTEGER DEFAULT 0;

COMMIT;

PRAGMA foreign_keys = ON;