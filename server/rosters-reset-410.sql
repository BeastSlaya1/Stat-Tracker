-- One-time reset of all normal and hidden team rosters. Match data is untouched.
CREATE TABLE IF NOT EXISTS release_migrations (id TEXT PRIMARY KEY);
UPDATE team_rosters
SET players = COALESCE((SELECT json_group_array(json_set(value, '$.active', json('false'))) FROM json_each(team_rosters.players)), '[]'),
    version = version + 1
WHERE NOT EXISTS (SELECT 1 FROM release_migrations WHERE id = 'rosters-reset-4.1.0');
INSERT OR IGNORE INTO release_migrations(id) VALUES ('rosters-reset-4.1.0');
