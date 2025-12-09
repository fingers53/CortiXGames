
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.security import (
    get_current_user,
    csrf_protected,
    assert_valid_username
)

import json
from datetime import datetime

from app.achievements import check_and_award_achievements


from app.db import get_db_connection
from app.achievements import check_and_award_achievements
from app.services.users import resolve_user_id
from app.services.geo import get_country_code_from_ip
from app.utils.validation import enforce_range

from app.services.memory_game import compute_memory_scores, fetch_memory_insights

router = APIRouter()

@router.post("/memory-game/submit_score")
async def submit_memory_score(
    request: Request, current_user=Depends(get_current_user), _=Depends(csrf_protected)
):
    data = await request.json()
    username = data.get("username")
    country_input = data.get("country") or data.get("countryCode")
    question_log = data.get("questionLog") or []

    if not current_user and username:
        assert_valid_username(username)

    if not isinstance(question_log, list) or not (1 <= len(question_log) <= 200):
        raise HTTPException(status_code=422, detail="Invalid question log length")

    for entry in question_log:
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail="Question entries must be objects")
        round_num = entry.get("round")
        seq_len = entry.get("sequenceLength")
        attempts = entry.get("attempts")
        was_correct = entry.get("wasCorrect")
        targets = entry.get("targets") or entry.get("targetCells") or []
        clicks = entry.get("clicks") or []
        if round_num not in (1, 2, 3):
            raise HTTPException(status_code=422, detail="Round must be between 1 and 3")
        if seq_len is None or not (1 <= seq_len <= 25):
            raise HTTPException(status_code=422, detail="Sequence length out of bounds")
        if attempts is None or attempts < 1:
            raise HTTPException(status_code=422, detail="Attempts must be at least 1")
        if was_correct not in (True, False):
            raise HTTPException(status_code=422, detail="Each question must include correctness")
        if targets and not all(isinstance(t, (list, tuple)) and len(t) >= 2 for t in targets):
            raise HTTPException(status_code=422, detail="Targets must be coordinates")
        if clicks and not all(isinstance(c, dict) for c in clicks):
            raise HTTPException(status_code=422, detail="Clicks must be objects")

    score_result = compute_memory_scores(question_log)
    total_score = max(0, score_result["total"])
    r1 = max(0, score_result["round1"])
    r2 = max(0, score_result["round2"])
    r3 = max(0, score_result["round3"])
    country_code = country_input or get_country_code_from_ip(request.client.host)

    enforce_range(total_score, 0, 200000, "Total score")
    enforce_range(r1, 0, 80000, "Round 1 score")
    enforce_range(r2, 0, 80000, "Round 2 score")
    enforce_range(r3, 0, 80000, "Round 3 score")

    response_payload = {
        "status": "success",
        "finalScore": total_score,
        "round1Score": r1,
        "round2Score": r2,
        "round3Score": r3,
        "nearMisses": score_result["near_misses"],
        "guessCount": score_result["guess_count"],
        "avgDurationMs": score_result["avg_duration_ms"],
        "avgIntervalMs": score_result["avg_interval_ms"],
    }

    if not current_user:
        response_payload["message"] = "Login to save your memory score"
        return JSONResponse(content=response_payload)

    conn = get_db_connection()
    try:
        user_id = resolve_user_id(conn, current_user, username, country_code)
        created_at = datetime.utcnow().isoformat()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO memory_scores (
                    user_id, total_score, round1_score, round2_score, round3_score, raw_payload, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    user_id,
                    total_score,
                    r1,
                    r2,
                    r3,
                    json.dumps(
                        {
                            "near_misses": score_result["near_misses"],
                            "guess_count": score_result["guess_count"],
                            "avg_duration_ms": score_result["avg_duration_ms"],
                            "avg_interval_ms": score_result["avg_interval_ms"],
                        }
                    ),
                    created_at,
                ),
            )
            inserted = cursor.fetchone()
            cursor.execute(
                "SELECT COALESCE(SUM(total_score), 0) FROM memory_scores WHERE user_id = %s",
                (user_id,),
            )
            running_total = cursor.fetchone()[0] or 0
        check_and_award_achievements(
            conn,
            user_id,
            "memory",
            {
                "total_score": total_score,
                "running_total": running_total,
                "created_at": inserted[1] if inserted else created_at,
            },
        )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(content=response_payload)
