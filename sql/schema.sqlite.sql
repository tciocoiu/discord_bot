-- Discord Loot Bot — SQLite schema
-- Tables are also created automatically on bot startup via SQLAlchemy.
-- Run manually: sqlite3 data/loot.db < sql/schema.sqlite.sql

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS loot_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id      INTEGER NOT NULL,
    channel_id    INTEGER NOT NULL,
    created_by_id INTEGER NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    people_json   TEXT NOT NULL,
    loot_json     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_loot_sessions_guild_id ON loot_sessions (guild_id);

CREATE TABLE IF NOT EXISTS loot_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES loot_sessions (id) ON DELETE CASCADE,
    person_key      VARCHAR(255) NOT NULL,
    display_name    VARCHAR(255) NOT NULL,
    discord_user_id INTEGER,
    loot_item       VARCHAR(500) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_loot_assignments_session_id ON loot_assignments (session_id);

CREATE TABLE IF NOT EXISTS user_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        INTEGER NOT NULL,
    person_key      VARCHAR(255) NOT NULL,
    display_name    VARCHAR(255) NOT NULL DEFAULT '',
    discord_user_id INTEGER,
    loot_count      INTEGER NOT NULL DEFAULT 0,
    miss_streak     INTEGER NOT NULL DEFAULT 0,
    activity_points INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT uq_guild_person UNIQUE (guild_id, person_key)
);

CREATE INDEX IF NOT EXISTS ix_user_stats_guild_id ON user_stats (guild_id);

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id          INTEGER PRIMARY KEY,
    alert_channel_id  INTEGER
);

CREATE TABLE IF NOT EXISTS boss_definitions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    name       VARCHAR(100) NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT uq_guild_boss_name UNIQUE (guild_id, name)
);

CREATE INDEX IF NOT EXISTS ix_boss_definitions_guild_id ON boss_definitions (guild_id);

CREATE TABLE IF NOT EXISTS boss_timers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id      INTEGER NOT NULL,
    boss_id       INTEGER NOT NULL REFERENCES boss_definitions (id) ON DELETE CASCADE,
    started_by_id INTEGER NOT NULL,
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    respawn_at    TEXT NOT NULL,
    CONSTRAINT uq_boss_timer UNIQUE (boss_id)
);

CREATE INDEX IF NOT EXISTS ix_boss_timers_guild_id ON boss_timers (guild_id);
CREATE INDEX IF NOT EXISTS ix_boss_timers_boss_id ON boss_timers (boss_id);

CREATE TABLE IF NOT EXISTS boss_panels (
    guild_id   INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL
);
