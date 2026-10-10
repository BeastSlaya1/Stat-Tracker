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
