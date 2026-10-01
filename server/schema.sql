PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'staff' CHECK(role IN ('admin','staff','user')),
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS login_attempts (
  key TEXT PRIMARY KEY, count INTEGER NOT NULL, reset_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY,
  body TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  deleted INTEGER NOT NULL DEFAULT 0,
  mutation_id TEXT NOT NULL,
  owner_id TEXT REFERENCES users(id),
  updated_by TEXT NOT NULL REFERENCES users(id),
  updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS catalog (
  table_name TEXT PRIMARY KEY,
  version INTEGER NOT NULL DEFAULT 1,
  rows_json TEXT NOT NULL
);

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
