CREATE TABLE IF NOT EXISTS camera_links (
 code TEXT PRIMARY KEY,
 owner_session TEXT NOT NULL UNIQUE,
 receiver_session TEXT,
 name TEXT NOT NULL,
 kind TEXT NOT NULL,
 receiver_name TEXT,
 approved INTEGER NOT NULL DEFAULT 0,
 offer TEXT NOT NULL,
 answer TEXT,
 last_seen INTEGER NOT NULL,
 expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS camera_links_seen ON camera_links(last_seen);
