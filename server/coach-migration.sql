CREATE TABLE IF NOT EXISTS coach_assignments (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 team_code TEXT NOT NULL,
 sport TEXT NOT NULL
);
