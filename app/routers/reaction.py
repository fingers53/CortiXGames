from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime

from app.security import (
    get_current_user,
    csrf_protected,
    assert_valid_username,
    render_template,   # if needed
)

from app.db import get_db_connection
from app.achievements import check_and_award_achievements
from app.services.users import resolve_user_id
from app.services.geo import get_country_code_from_ip
from app.utils.validation import enforce_range

# GAME-SPECIFIC imports
from app.services.reaction_game import (
    calculate_reaction_game_score,
    validate_answer_record,
    fetch_reaction_insights,
)


router = APIRouter()

@router.post("/reaction-game/submit_score")
async def submit_reaction_score(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    data = await request.json()
    username = data.get("username")
    country_input = data.get("country") or data.get("countryCode")
    score_data = data.get("scoreData") or {}
    answer_record = score_data.get("answerRecord") or []

    if not current_user and username:
        assert_valid_username(username)
    validate_answer_record(answer_record)

    score_result = calculate_reaction_game_score(answer_record)
    country_code = country_input or get_country_code_from_ip(request.client.host)
    final_score = score_result["finalScore"]
    average_time_ms = score_result["averageTime"]
    fastest_time_ms = score_result["fastestTime"]
    slowest_time_ms = score_result["slowestTime"]
    accuracy = score_result["accuracy"]

    enforce_range(final_score, -5000, 20000, "Final score")
    enforce_range(average_time_ms, 0, 5000, "Average time")
    enforce_range(fastest_time_ms, 50, 5000, "Fastest time")
    enforce_range(slowest_time_ms, 50, 5000, "Slowest time")
    enforce_range(accuracy, 0, 100, "Accuracy")

    if not current_user:
        return JSONResponse(
            content={
                "status": "success",
                "scoreResult": score_result,
                "message": "Login to save your reaction score",
            }
        )

    conn = get_db_connection()
    try:
        user_id = resolve_user_id(conn, current_user, username, country_code)
        created_at = datetime.utcnow().isoformat()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reaction_scores (
                    user_id, score, average_time_ms, fastest_time_ms,
                    slowest_time_ms, accuracy, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    user_id,
                    final_score,
                    average_time_ms,
                    fastest_time_ms,
                    slowest_time_ms,
                    accuracy,
                    created_at,
                ),
            )
            inserted = cursor.fetchone()
        check_and_award_achievements(
            conn,
            user_id,
            "reaction",
            {
                "average_time_ms": average_time_ms,
                "accuracy": accuracy,
                "created_at": inserted[1] if inserted else created_at,
            },
        )
        conn.commit()
    finally:
        conn.close()


    return JSONResponse(content={"status": "success", "scoreResult": score_result})

