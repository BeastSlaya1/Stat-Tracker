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
