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

CREATE TABLE IF NOT EXISTS signin_methods (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 email_address TEXT,
 sms_address TEXT,
 authenticator_login INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS signin_challenges (
 id TEXT PRIMARY KEY,
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 channel TEXT NOT NULL,
 destination TEXT NOT NULL,
 provider_sid TEXT NOT NULL,
 purpose TEXT NOT NULL,
 session_hash TEXT NOT NULL DEFAULT '',
 expires_at INTEGER NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS signin_challenges_expiry ON signin_challenges(expires_at);
-- Contact, password and authenticator changes invalidate outstanding sign-in codes.
CREATE TRIGGER IF NOT EXISTS signin_account_changed AFTER UPDATE OF email,password_hash,enabled,role ON users
BEGIN
 DELETE FROM signin_challenges WHERE user_id=NEW.id;
 UPDATE signin_methods SET
   email_address=CASE WHEN OLD.email IS NOT NEW.email OR OLD.password_hash IS NOT NEW.password_hash THEN NULL ELSE email_address END,
   sms_address=CASE WHEN OLD.password_hash IS NOT NEW.password_hash THEN NULL ELSE sms_address END,
   authenticator_login=CASE WHEN OLD.password_hash IS NOT NEW.password_hash THEN 0 ELSE authenticator_login END
 WHERE user_id=NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS signin_contact_changed AFTER UPDATE OF phone,secret ON account_security
WHEN OLD.phone IS NOT NEW.phone OR OLD.secret IS NOT NEW.secret
BEGIN
 DELETE FROM signin_challenges WHERE user_id=NEW.user_id;
 UPDATE signin_methods SET
   sms_address=CASE WHEN OLD.phone IS NOT NEW.phone THEN NULL ELSE sms_address END,
   authenticator_login=CASE WHEN OLD.secret IS NOT NEW.secret THEN 0 ELSE authenticator_login END
 WHERE user_id=NEW.user_id;
END;

CREATE TABLE IF NOT EXISTS auth0_links (
 issuer TEXT NOT NULL,
 subject TEXT NOT NULL,
 user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
 PRIMARY KEY(issuer,subject)
);
CREATE TABLE IF NOT EXISTS auth0_flows (
 ticket_hash TEXT PRIMARY KEY,
 state_hash TEXT NOT NULL UNIQUE,
 client_id TEXT NOT NULL,
 challenge TEXT NOT NULL,
 nonce TEXT NOT NULL,
 redirect_uri TEXT NOT NULL,
 purpose TEXT NOT NULL,
 user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
 session_hash TEXT NOT NULL DEFAULT '',
 expires_at INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',
 code TEXT
);
CREATE INDEX IF NOT EXISTS auth0_flows_expiry ON auth0_flows(expires_at);
CREATE TRIGGER IF NOT EXISTS auth0_account_changed AFTER UPDATE OF password_hash,enabled,role,email ON users
BEGIN
 DELETE FROM auth0_flows WHERE user_id=NEW.id;
END;
