ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'staff' CHECK(role IN ('admin','staff','user'));
ALTER TABLE matches ADD COLUMN owner_id TEXT REFERENCES users(id);
UPDATE matches SET owner_id=updated_by WHERE owner_id IS NULL;
ALTER TABLE catalog ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS matches_owner ON matches(owner_id,id);
