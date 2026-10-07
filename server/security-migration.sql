CREATE TABLE IF NOT EXISTS account_security (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 phone TEXT NOT NULL DEFAULT '',
 secret TEXT,
 pending TEXT,
 pending_expires INTEGER NOT NULL DEFAULT 0,
 pending_session TEXT,
 last_step INTEGER NOT NULL DEFAULT -1,
 recovery_hashes TEXT NOT NULL DEFAULT '[]'
);
