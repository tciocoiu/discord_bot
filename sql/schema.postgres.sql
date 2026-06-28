-- Discord Loot Bot — PostgreSQL schema (Railway)
-- Tables are also created automatically on bot startup via SQLAlchemy.
-- Run manually: psql $DATABASE_URL -f sql/schema.postgres.sql

CREATE TABLE IF NOT EXISTS loot_sessions (
    id            SERIAL PRIMARY KEY,
    guild_id      BIGINT NOT NULL,
    channel_id    BIGINT NOT NULL,
    created_by_id BIGINT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    people_json   TEXT NOT NULL,
    loot_json     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_loot_sessions_guild_id ON loot_sessions (guild_id);

CREATE TABLE IF NOT EXISTS loot_assignments (
    id              SERIAL PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES loot_sessions (id) ON DELETE CASCADE,
    person_key      VARCHAR(255) NOT NULL,
    display_name    VARCHAR(255) NOT NULL,
    discord_user_id BIGINT,
    loot_item       VARCHAR(500) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_loot_assignments_session_id ON loot_assignments (session_id);

CREATE TABLE IF NOT EXISTS user_stats (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    person_key      VARCHAR(255) NOT NULL,
    display_name    VARCHAR(255) NOT NULL DEFAULT '',
    discord_user_id BIGINT,
    loot_count      INTEGER NOT NULL DEFAULT 0,
    miss_streak     INTEGER NOT NULL DEFAULT 0,
    activity_points INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_guild_person UNIQUE (guild_id, person_key)
);

CREATE INDEX IF NOT EXISTS ix_user_stats_guild_id ON user_stats (guild_id);
