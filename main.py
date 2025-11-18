from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
from scoring import calculate_reaction_game_score

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Helper function to read HTML files
def read_html(file_name):
    with open(f"templates/{file_name}") as f:
        return f.read()

# Routes for HTML pages
@app.get("/", response_class=HTMLResponse)
async def landing_page():
    return HTMLResponse(content=read_html("landing_page.html"))

@app.get("/memory-game", response_class=HTMLResponse)
async def memory_game():
    return HTMLResponse(content=read_html("memory_game.html"))

@app.get("/reaction-game", response_class=HTMLResponse)
async def reaction_game():
    return HTMLResponse(content=read_html("reaction_game.html"))

@app.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard():
    return HTMLResponse(content=read_html("leaderboard.html"))

@app.get("/leaderboard/reaction-game", response_class=HTMLResponse)
async def reaction_game_leaderboard():
    return HTMLResponse(content=read_html("reaction_leaderboard.html"))

@app.get("/leaderboard/memory-game", response_class=HTMLResponse)
async def memory_game_leaderboard():
    return HTMLResponse(content=read_html("memory_leaderboard.html"))

# Database helper functions
def get_or_create_user(username: str, ip_address: str):
    conn = sqlite3.connect("scores.sqlite3")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if user:
        user_id = user[0]
    else:
        cursor.execute(
            "INSERT INTO users (username, ip_address) VALUES (?, ?)",
            (username, ip_address)
        )
        conn.commit()
        user_id = cursor.lastrowid
    
    conn.close()
    return user_id

def submit_score(game_table: str, user_id: int, score: int, avg_reaction_time: float, accuracy:float):
    conn = sqlite3.connect("scores.sqlite3")
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO {game_table} (user_id, score, avg_reaction_time,accuracy) VALUES (?, ?, ?)",
        (user_id, score, avg_reaction_time)
    )
    conn.commit()
    conn.close()

# Endpoints for submitting scores
#FIXME
@app.post("/submit_score/{game}")
async def submit_score_endpoint(game: str, request: Request):
    data = await request.json()
    username = data.get("username")
    score = data.get("score")
    avg_reaction_time = data.get("avgReactionTime")
    accuracy = data.get("accuracy")

    if not username or score is None:
        return JSONResponse(content={"status": "error", "message": "Missing required fields"}, status_code=400)

    ip_address = request.client.host

    # Get or create user
    user_id = get_or_create_user(username, ip_address)

    # Select appropriate table and submit score
    if game == "reaction-game":
        if avg_reaction_time is None or accuracy is None:
            return JSONResponse(content={"status": "error", "message": "Missing reaction game fields"}, status_code=400)
        submit_score("reaction_scores", user_id, score, avg_reaction_time, accuracy)
        print(f"Reaction Game - Username: {username}, Score: {score}, Avg Reaction Time: {avg_reaction_time} ms, Accuracy: {accuracy}%")
    elif game == "memory-game":
        if avg_reaction_time is None:
            return JSONResponse(content={"status": "error", "message": "Missing memory game fields"}, status_code=400)
        submit_score("memory_scores", user_id, score, avg_reaction_time, 0) # Memory game doesn't use accuracy
        print(f"Memory Game - Username: {username}, Score: {score}, Avg Reaction Time: {avg_reaction_time} ms")
    else:
        return JSONResponse(content={"status": "error", "message": "Invalid game type"}, status_code=400)

    return {"status": "success", "message": f"{game.replace('-', ' ').title()} score submitted successfully"}

# Leaderboard API endpoints
@app.get("/api/leaderboard/{game}")
async def leaderboard_api(game: str):
    conn = sqlite3.connect("scores.sqlite3")
    cursor = conn.cursor()

    try:
        if game == "reaction-game":
            cursor.execute("""
                SELECT u.username, r.score, r.avg_reaction_time, r.accuracy
                FROM reaction_scores r
                JOIN users u ON r.user_id = u.id
                ORDER BY r.score DESC
                LIMIT 10
            """)
        elif game == "memory-game":
            cursor.execute("""
                SELECT u.username, m.score, m.avg_reaction_time
                FROM memory_scores m
                JOIN users u ON m.user_id = u.id
                ORDER BY m.score DESC
                LIMIT 10
            """)
        else:
            return JSONResponse(content={"status": "error", "message": "Invalid game type"}, status_code=400)

        scores = cursor.fetchall()
        return JSONResponse(content={"scores": scores})
    except sqlite3.Error as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)
    finally:
        conn.close()

@app.post("/reaction-game/submit_score")
async def submit_reaction_score(request: Request):
    data = await request.json()
    score_data = data.get("scoreData")

    # Calculate the score
    score_result = calculate_reaction_game_score(score_data)

    # Save the score to the database (if applicable)
    # Example: save_score_to_db(score_result)

    return JSONResponse(content={"status": "success", "scoreResult": score_result})
