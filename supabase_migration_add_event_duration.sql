-- Add event_duration to event table (run if table already exists without this column)
ALTER TABLE event
ADD COLUMN IF NOT EXISTS event_duration INTEGER NOT NULL DEFAULT 60;
