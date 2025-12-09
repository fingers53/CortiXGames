# CortiX Games

CortiX Games is a FastAPI + Jinja2 web app backed by Postgres (Supabase-friendly) with lightweight authentication and several arcade-style games:

- **Memory** – grid recall across multiple rounds.
- **Reaction** – left/right matching with timing stats.
- **Arithmetic** – a three-round flow (Rounds 1–3) with leaderboard, stats, and per-question analytics.

Authentication uses signed session cookies (username + password), and all scores are persisted to Postgres tables (no SQLite files required).

## Project structure

```
CortiXGames/
├─ app/
│   ├─ routers/
│   └─ …
├─ templates/
│   ├─ landing_page.html
│   ├─ profile/
│   ├─ reaction/
│   ├─ memory/
│   └─ maths/
├─ static/
│   ├─ css/
│   ├─ js/
│   ├─ reaction/
│   ├─ memory/
│   └─ maths/
└─ main.py
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
