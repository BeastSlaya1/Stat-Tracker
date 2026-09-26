CREATE TABLE IF NOT EXISTS camera_rooms (
  code TEXT PRIMARY KEY,
  owner_session TEXT NOT NULL,
  owner_id TEXT NOT NULL UNIQUE,
  receiver_session TEXT,
  receiver_name TEXT,
  approved INTEGER NOT NULL DEFAULT 0,
  offer TEXT NOT NULL,
  answer TEXT,
  expires_at INTEGER NOT NULL
);
