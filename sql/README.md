# SQL schema

Reference SQL for the Discord Loot Bot database. The bot **creates these tables automatically** on startup — you usually don't need to run these scripts manually.

## Files

| File | Database |
|------|----------|
| [`schema.sqlite.sql`](schema.sqlite.sql) | SQLite (local dev, `data/loot.db`) |
| [`schema.postgres.sql`](schema.postgres.sql) | PostgreSQL (Railway) |

## Tables

```
loot_sessions       — one row per /spread-loot run
loot_assignments    — who received what (FK → loot_sessions)
user_stats          — per-guild bad luck + activity tracking
guild_settings      — alert channel for boss timers
boss_definitions    — boss names per guild
boss_timers         — active 4h respawn timers
boss_panels         — panel message reference for embed refresh
```

## Manual apply (optional)

**SQLite:**
```bash
mkdir -p data
sqlite3 data/loot.db < sql/schema.sqlite.sql
```

**PostgreSQL (Railway):**
```bash
psql "$DATABASE_URL" -f sql/schema.postgres.sql
```

## Inspect local SQLite

```bash
sqlite3 data/loot.db
```

Example queries:
```sql
SELECT * FROM loot_sessions ORDER BY created_at DESC LIMIT 5;
SELECT * FROM user_stats WHERE guild_id = YOUR_GUILD_ID;
SELECT la.display_name, la.loot_item
FROM loot_assignments la
JOIN loot_sessions ls ON ls.id = la.session_id
ORDER BY ls.created_at DESC;
```
