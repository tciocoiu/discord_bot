# Discord Loot Bot

A Discord bot for weighted loot distribution with bad-luck protection, activity boosts, and session history. Deployed on Railway with PostgreSQL.

## Commands

| Command | Description |
|---------|-------------|
| `/spread-loot` | Opens a modal — people, loot, optional activity points per winner + reason. |
| `/add-activity` | Add activity points to a user (requires Manage Server). Boosts their loot chance. |
| `/show-activity` | Show activity points for all tracked members in the server. |
| `/show-logs` | Show all loot distributed in the past 7 days. |
| `/wipe` | Reset activity points and bad-luck streaks (server owner only). Loot history kept. |
| `/help` | List all commands, who can use them, and what they do. |

### Boss timers

| Command | Description |
|---------|-------------|
| `/set-boss-alerts` | Set channel for 10-minute warnings and boss-up alerts (admin). |
| `/add-boss` | Add a boss name to the panel (admin). |
| `/remove-boss` | Remove a boss (admin). |
| `/list-bosses` | Show all bosses and their current timer status. |
| `/boss-panel` | Post button panel — anyone can click to start a 4h timer (admin). |

**Setup:** `/set-boss-alerts #alerts` → `/add-boss` for each boss → `/boss-panel` in your timer channel.

Alerts post to the alert channel at **10 minutes left** and when the boss is **up**. The boss panel auto-refreshes every second while timers are running. Max 25 bosses per server.

## How weighting works

Each person's chance per loot roll:

```
weight = BASE_WEIGHT + (miss_streak × BAD_LUCK_WEIGHT) + (activity_points × ACTIVITY_WEIGHT)
```

Defaults: `BASE_WEIGHT=1.0`, `BAD_LUCK_WEIGHT=0.5`, `ACTIVITY_WEIGHT=0.1`

- **Bad luck protection:** `miss_streak` increases each session someone gets nothing; resets on win.
- **Activity:** Points from `/add-activity` persist and increase weight (not consumed on win).

Use Discord mentions (`@User`) in the people list to track stats by user ID.

**Splittable loot:** Lines starting with a number greater than 1 (e.g. `400 bes`) are divided evenly among everyone in the people list. Any remainder is assigned using the same weighted random rules. Single items (e.g. `Rare gem`) still go to one winner.

## Database

- **Local dev:** SQLite file at `data/loot.db` (default, no Postgres needed)
- **Railway:** PostgreSQL — add the Postgres plugin and link `DATABASE_URL`

The `data/` folder is created automatically on first run.

Schema reference SQL lives in [`sql/`](sql/) (SQLite + PostgreSQL). Tables are still created by the bot on startup — the SQL files are for manual setup or inspection.

## Local setup

1. **Python 3.12+**

2. **Install dependencies:**
   ```bash
   cd discord-loot-bot
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   copy .env.example .env
   ```
   Edit `.env`:
   - `DISCORD_TOKEN` — from [Discord Developer Portal](https://discord.com/developers/applications)
   - `DATABASE_URL` — optional; defaults to SQLite at `data/loot.db`. For Railway, use the linked Postgres URL.

4. **Create Discord application:**
   - New Application → Bot → copy token
   - OAuth2 → URL Generator → scopes: `bot`, `applications.commands`
   - Bot permissions: Send Messages, Use Slash Commands, Embed Links

5. **Run:**
   ```bash
   python -m bot
   ```

## Railway deployment

The repo is ready to deploy — no extra code needed. You configure everything in Railway + Discord.

### Checklist

1. Push this repo to **GitHub** (root must contain `requirements.txt`, `railway.toml`, `bot/`).
2. [Railway](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. In the same project → **+ New** → **Database** → **PostgreSQL**.
4. Open your **bot service** → **Variables**:
   - `DISCORD_TOKEN` = your Discord bot token
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (use Railway variable reference / Connect)
5. Deploy. Start command is already `python -m bot` in `railway.toml`.
6. Invite the bot to your server (OAuth2 → `bot` + `applications.commands` scopes).
7. Check **Deploy Logs** for `Logged in as ...` and `Slash commands synced`.

You do **not** need to run SQL scripts — tables are created on first boot.

Do **not** use SQLite on Railway unless you add a persistent Volume. Use PostgreSQL.

### If deploy fails

| Log error | Fix |
|-----------|-----|
| `DISCORD_TOKEN environment variable is required` | Add `DISCORD_TOKEN` in Railway Variables |
| Database connection error | Link `DATABASE_URL` from Postgres service |
| Bot online but no slash commands | Re-invite with `applications.commands` scope; wait ~1 min |

## Optional tuning

Set these in Railway variables or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_WEIGHT` | `1.0` | Base loot roll weight |
| `BAD_LUCK_WEIGHT` | `0.5` | Extra weight per miss streak |
| `ACTIVITY_WEIGHT` | `0.1` | Extra weight per activity point |

## Project structure

```
bot/
├── __main__.py       # Entry point
├── config.py         # Env config
├── cogs/
│   ├── loot.py       # /spread-loot, /show-logs
│   ├── activity.py   # /add-activity, /show-activity, /wipe
│   ├── bosses.py     # Boss timer panel + admin commands
│   └── help.py       # /help
├── db/
│   ├── engine.py     # SQLAlchemy async engine
│   └── models.py     # Sessions, assignments, user stats, bosses
└── services/
    ├── loot_engine.py   # Weighted distribution
    ├── loot_service.py  # Persistence + logs
    ├── activity.py      # Activity points
    └── boss_timers.py   # Boss timer scheduling + panel
sql/
├── schema.sqlite.sql    # SQLite schema (local)
├── schema.postgres.sql  # PostgreSQL schema (Railway)
└── README.md
```
