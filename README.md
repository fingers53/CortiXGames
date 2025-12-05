# CortiX Games

CortiX Games is a FastAPI + Jinja2 web app backed by Postgres (Supabase-friendly) with lightweight authentication and several arcade-style games:

- **Memory** – grid recall across multiple rounds.
- **Reaction** – left/right matching with timing stats.
- **Arithmetic** – a two-round flow (Yetamax then Maveric) with leaderboard, stats, and per-question analytics.

Authentication uses signed session cookies (username + password), and all scores are persisted to Postgres tables (no SQLite files required).

## Project structure

```
app/                 # New application package: config, db helpers, routers, services
math-games/          # Arithmetic templates and static assets (round 1 + round 2)
static/              # Shared assets, grouped by game under static/games/
  games/
    memory/          # Memory JS/CSS modules
    reaction/        # Reaction JS/CSS
templates/           # Jinja templates
  games/             # Memory/Reaction gameplay templates
  leaderboards/      # Shared leaderboard pages
README.md            # This file
main.py              # FastAPI entrypoint (mounts templates/static, routes)
requirements.txt     # Python dependencies
```

## Running locally

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables (e.g. `DATABASE_URL`, `SESSION_COOKIE_SECURE`). Supabase Postgres URLs work out of the box.
4. Start the dev server:

```bash
uvicorn main:app --reload
```

Visit `http://127.0.0.1:8000/` for the landing page. The arithmetic experience lives at `/math-game`, memory at `/memory-game`, reaction at `/reaction-game`, and leaderboards under `/leaderboard` and `/math-game/leaderboard`.

## Notes

- Legacy SQLite helpers and files have been removed; the app now expects Postgres/Supabase for all persistence.
- Arithmetic assets live under `math-games/` to keep round-specific templates and static files isolated from other games.
- The `app/` package is being introduced progressively to untangle `main.py`; both coexist while routes are migrated.
