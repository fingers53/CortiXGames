# Quanty JavaScript Games

Small browser-based brain games backed by a FastAPI API and a SQLite leaderboard.  
Built mainly as a portfolio / CV piece and as a playground for async + JS game logic.

You (future you) will probably have forgotten all of this, so here’s how it works and how to get it running again without wanting to delete the repo.

---

## 1. What this project is

Two simple games, run in the browser, with a Python backend that:

- Serves the HTML templates and static assets
- Stores scores in a SQLite database
- Exposes leaderboards and “best score” APIs

Games:

1. **Memory game**
   - Grid-based patterns you have to remember and reproduce.
   - Multiple rounds, distractions, and a custom scoring system.
   - Scores are written to `memory_scores` (or equivalent) in `scores.sqlite3`.
   - The landing page can show “Best Memory” for the current username.

2. **Reaction game**
   - Three balls: left, center, right.
   - Center ball matches either left or right; you must pick the matching side as fast as possible.
   - Keys: `1` = **left**, `0` = **right**, plus on‑screen buttons for mobile.
   - Tracks reaction stats: correct/incorrect, average time, fastest/slowest, streak penalties, etc.
   - Scores written to `reaction_scores` table, and exposed in the leaderboards + best-score API.

User identity is deliberately lightweight:

- No login system.
- You pick a **username** on the landing page.
- Username is stored in `localStorage` (`username` key).
- Backend trusts the provided username and records scores under that user.

This is **good enough for friends testing it** and for a portfolio piece, not for production-grade security.

---

## 2. Tech stack & structure

### Backend

- **Python** + **FastAPI**
- **Uvicorn** for local dev server
- **SQLite** (`scores.sqlite3`) for persistence
- Basic IP → country handling for flags (currently not working as intended; see Known Issues).

Main files in the root:

- `main.py`  
  FastAPI app, routes, template rendering, static mounting, score submission endpoints, leaderboard APIs, and “best scores” API.

- `creating_db.py` / `scoring.py` (names may vary slightly)  
  Utility / setup scripts for initializing or adjusting the SQLite schema.

- `scores.sqlite3`  
  The current leaderboard DB. On Render this is **ephemeral** unless you wire persistent disk.

### Frontend

- **Templates** (Jinja2 / standard HTML) in `/templates`
  - `landing_page.html`
  - `memory_game.html`
  - `reaction_game.html`
  - `*_leaderboard.html` variants

- **Static assets** in `/static`
  - `memory_game.js`, `reaction_game.js`, `gameFlow.js`, etc.
  - `memory_game.css`, `reaction_game.css`, `styles.css`
  - Any icons / future favicon.

- **`main.js`** (landing page)
  - Handles username input, validation, saving to `localStorage`.
  - Wires buttons to `/memory-game` and `/reaction-game` routes.
  - Fetches `/api/my-best-scores?username=...` and conditionally shows:
    - **Best Reaction** (if exists)
    - **Best Memory** (if exists)

---

## 3. How to run this locally

Assumes Python 3.11+ and `pip` installed.

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# If you ever need to recreate the DB schema:
# python creating_db.py   # (only if you know what it does)

uvicorn main:app --reload
```

Then open:

- `http://127.0.0.1:8000/` → landing page
- Buttons go to:
  - `/memory-game`
  - `/reaction-game`
- Leaderboards:
  - `/leaderboard/memory-game`
  - `/leaderboard/reaction-game`

If something explodes on DB access, check `creating_db.py` or the schema in `main.py` and make sure `scores.sqlite3` exists and has the right tables.

---

## 4. How usernames & scores work

### Username flow

- Landing page has an `<input id="username">` and `<button id="enter-button">`.
- `main.js`:
  - Validates username via regex: `^[A-Za-z0-9_]{3,20}$`.
  - Saves it in `localStorage["username"]`.
  - Disables the input once confirmed.
  - Hides the enter button once a valid username is set.
- Game pages rely on `localStorage["username"]` for POSTing scores.

If there is no valid username:

- Navigation buttons (`Memory`, `React`) will alert and refuse to route.

### Best scores on landing page

`main.js` calls:

```js
GET /api/my-best-scores?username=...
```

Backend returns user’s best reaction / memory result (or null).

Frontend:

- Hides the best-score box by default.
- Shows it only when there’s at least one score.
- This avoids ugly `–` placeholders and encoding garbage like `â€“`.

---

## 5. Leaderboards: what they do and known issues

There are separate leaderboard endpoints / templates for:

- Memory game
- Reaction game

The HTML should show:

- Rank
- Username
- Score(s)
- Country flag (in theory)
- Created_at / time info (depending on template)

### Known issue 1 — Leaderboard resets on Render sleep

**Symptom:** every time Render “sleeps” the app, the leaderboard is empty when it wakes.

**Cause (almost certainly):**

- You’re using **SQLite on ephemeral disk** in Render.
- When the container stops, the `scores.sqlite3` file is blown away.
- New container = fresh DB file, no rows.

**Fix options (future you):**

1. **Use a real database**:
   - Provision Postgres on Render (or Supabase, Railway, etc.).
   - Migrate the schema from SQLite to Postgres.
   - Update DB connection in `main.py`.
   - This is the clean, scalable approach.

2. **Persistent disk (if Render supports it the way you need)**:
   - Mount a persistent volume and put `scores.sqlite3` there.
   - Confirm that the volume survives container restarts.

3. **Accept it for now**:
   - For a CV/demo project, it’s honestly fine if scores reset between sleeps.
   - Just mention in README (this file) that it’s a hosting limitation, not a bug.

### Known issue 2 — Flags show `??`

Leaderboards currently display `??` instead of real country flags.

Likely reasons:

- Country detection falls back to `"??"` or `"Unknown"` because:
  - No real IP-geolocation being done (e.g. on Render, `X-Forwarded-For` is internal).
  - You’re not mapping IP → country at all, or the code always returns a default.
- The template expects an emoji flag from a 2-letter country code, but only ever receives `"??"`.

**Future fix ideas:**

- Use a proper geolocation service (IP2Location, MaxMind, ipinfo, etc.).
- Store just a 2-letter **country code** in the DB (`"IE"`, `"GB"`, `"ES"`, etc.).
- Render flags as emoji via regional indicator symbols, or use static country-flag SVGs.
- For local / dev, you can just hardcode `"IE"` or something for testing.

---

## 6. Future features / ideas

Stuff you explicitly wanted to maybe do later:

### 1. Zetamac-style third game

A mental arithmetic game:

- 60 seconds.
- Simple questions:
  - 2-digit and 3-digit addition / subtraction
  - Maybe easy multiplication and modulo.
- Score = number of correct answers.
- Optional Elo-like rating or streak-based scoring.

Rough plan:

- New HTML: `templates/math_game.html`
- New JS: `static/math_game.js`
- New DB table: `yetamax_scores`
- Shared username + leaderboard logic re-usable.

### 2. Improve memory game scoring

Current memory scoring is probably “correct minus incorrect” with some tweaks.

Ideas:

- Penalize **slow** but correct answers.
- Reward streaks of perfect rounds.
- Increase difficulty over time and weight later rounds more.
- Track:
  - total patterns shown
  - total correct
  - total misclicks
  - average time to complete each pattern

Expose a breakdown on the end screen like you did for reaction game.

### 3. Better persistence + analytics

- Move scores to Postgres.
- Track:
  - browser / device type
  - approximate location (country only, not IP)
  - number of sessions per user
- Add an admin-only dashboard to see:
  - usage over time
  - average scores
  - distribution of reaction times.

---

## 7. Quick dev notes & gotchas

- **Don’t touch game logic lightly.**  
  Memory game and reaction game both have a lot of timing / visibility / state transitions:
  - `setTimeout`, `setInterval`
  - flags like `middleBallShown`, `lockInput`, etc.
  Small changes can cause rounds to “freeze” if a timeout is cleared too soon.

- **If a game “freezes” between rounds**, always open browser dev tools (F12 → Console) and look for:
  - `Uncaught TypeError`
  - `Cannot read properties of null`
  - etc.  
  That usually points straight to the cause.

- **Landing page JS (`main.js`) only runs on `/`**, not on game routes.  
  So any weirdness in a game screen is almost never caused by landing-page changes.

- **Favicon 404 in logs is harmless.**  
  If you want to silence it, add `/static/favicon.ico` and a `<link rel="icon"...>` in the `<head>`.

---

## 8. How to deploy again (high-level)

Rough Render steps you probably followed:

1. Push repo to GitHub.
2. Create a new **Web Service** in Render tied to the repo.
3. Build command:
   - `pip install -r requirements.txt`
4. Start command:
   - `uvicorn main:app --host 0.0.0.0 --port 10000`  
     (or whatever port Render expects / you configured)
5. Expose the URL to friends.

Remember:

- SQLite on Render is not persistent across sleeps unless you configure a persistent volume.
- That explains the leaderboard reset.

---

## 9. TL;DR for Future You

When you come back months from now:

1. **To run locally**:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `uvicorn main:app --reload`
   - Open `http://127.0.0.1:8000/`

2. **Known issues**:
   - Leaderboard wipes when Render sleeps (SQLite on ephemeral disk).
   - Flags show `??` (no real geo implemented).

3. **Future work**:
   - Add a Zetamac-style math game.
   - Improve memory-game scoring breakdown.
   - Migrate scores to Postgres + fix flags properly.

If it’s for CV / demo purposes, it’s already more than enough:  
two games, usernames, per-user best scores, leaderboards, deployed backend. Definitely shippable.
