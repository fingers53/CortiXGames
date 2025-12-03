ALTER TABLE users
ADD COLUMN IF NOT EXISTS password_hash TEXT;

ALTER TABLE users
ADD CONSTRAINT IF NOT EXISTS users_username_key UNIQUE (username);
