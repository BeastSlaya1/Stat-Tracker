CREATE TABLE IF NOT EXISTS account_access (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 owner INTEGER NOT NULL DEFAULT 0 CHECK(owner IN (0,1)),
 hidden INTEGER NOT NULL DEFAULT 0 CHECK(hidden IN (0,1)),
 can_grant_owner INTEGER NOT NULL DEFAULT 0 CHECK(can_grant_owner IN (0,1))
);
CREATE TABLE IF NOT EXISTS match_privacy (
 match_id TEXT PRIMARY KEY REFERENCES matches(id) ON DELETE CASCADE,
 hidden INTEGER NOT NULL DEFAULT 0 CHECK(hidden IN (0,1))
);
INSERT OR IGNORE INTO match_privacy(match_id,hidden) SELECT id,0 FROM matches;
CREATE TRIGGER IF NOT EXISTS match_privacy_create AFTER INSERT ON matches BEGIN
 INSERT INTO match_privacy(match_id,hidden) VALUES(NEW.id,COALESCE((SELECT hidden FROM account_access WHERE user_id=NEW.owner_id),0));
END;
-- Hiding an account also hides its existing authored or last-edited matches.
-- Previously private matches remain private when an account is made public.
CREATE TRIGGER IF NOT EXISTS account_hide_insert AFTER INSERT ON account_access WHEN NEW.hidden=1 BEGIN
 UPDATE match_privacy SET hidden=1 WHERE match_id IN (SELECT id FROM matches WHERE owner_id=NEW.user_id OR updated_by=NEW.user_id);
END;
CREATE TRIGGER IF NOT EXISTS account_hide_update AFTER UPDATE OF hidden ON account_access WHEN NEW.hidden=1 BEGIN
 UPDATE match_privacy SET hidden=1 WHERE match_id IN (SELECT id FROM matches WHERE owner_id=NEW.user_id OR updated_by=NEW.user_id);
END;

CREATE TRIGGER IF NOT EXISTS match_privacy_edit AFTER UPDATE ON matches
 WHEN COALESCE((SELECT hidden FROM account_access WHERE user_id=NEW.updated_by),0)=1 BEGIN
 UPDATE match_privacy SET hidden=1 WHERE match_id=NEW.id;
END;
