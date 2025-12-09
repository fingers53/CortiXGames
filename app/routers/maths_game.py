from datetime import datetime

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.security import get_current_user, csrf_protected
from app.db import get_db_connection
from app.utils.validation import enforce_range
from app.achievements import check_and_award_achievements
from app.services.maths_game import calculate_arithmetic_score

router = APIRouter()


async def save_round1_score(request: Request, current_user):
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    data = await request.json()
    correct_count = int(data.get("correct_count") or 0)
    wrong_count = int(data.get("wrong_count") or 0)
    avg_time_ms = float(data.get("avg_time_ms") or 0)
    min_time_ms = float(data.get("min_time_ms") or 0)
    per_question_times = data.get("per_question_times") or []
    avg_time_by_operator = data.get("avg_time_by_operator") or {}

    if correct_count < 0 or wrong_count < 0:
        raise HTTPException(status_code=422, detail="Counts must be non-negative")
    if correct_count > 200 or wrong_count > 200:
        raise HTTPException(status_code=422, detail="Counts too large")
    if len(per_question_times) > 400:
        raise HTTPException(status_code=422, detail="Too many timing entries")

    is_valid = not (min_time_ms < 150)
    enforce_range(avg_time_ms, 0, 10000, "Average time")
    enforce_range(min_time_ms, 50, 5000, "Minimum time")

    score_value = calculate_arithmetic_score(
        correct_count, wrong_count, avg_time_ms, per_question_times
    )

    enforce_range(score_value, -2000, 50000, "Score")

    raw_payload = data.copy()
    raw_payload.update({"score": score_value, "is_valid": is_valid})

    response_payload = {
        "status": "success",
        "score": score_value,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "avg_time_ms": avg_time_ms,
        "min_time_ms": min_time_ms,
        "is_valid": is_valid,
        "avg_time_by_operator": avg_time_by_operator,
        "per_question_times": per_question_times,
    }

    # In practice current_user should always exist here (we guard earlier),
    # but keep this for safety / anonymous behaviour parity.
    if not current_user:
        response_payload["round1_score_id"] = None
        response_payload["message"] = "Login to save your Round 1 score"
        return JSONResponse(content=response_payload)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO math_round1_scores (
                    user_id, score, correct_count, wrong_count,
                    avg_time_ms, min_time_ms, is_valid, raw_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    current_user["id"],
                    score_value,
                    correct_count,
                    wrong_count,
                    avg_time_ms,
                    min_time_ms,
                    is_valid,
                    psycopg2.extras.Json(raw_payload),
                ),
            )
            inserted = cursor.fetchone()
            new_id = inserted[0]
        check_and_award_achievements(
            conn,
            current_user["id"],
            "math_round1",
            {
                "avg_time_ms": avg_time_ms,
                "wrong_count": wrong_count,
                "correct_count": correct_count,
                "created_at": inserted[1] if inserted else None,
            },
        )
        conn.commit()
    finally:
        conn.close()

    response_payload["round1_score_id"] = new_id
    return JSONResponse(content=response_payload)


async def _save_round_mixed_score(
    request: Request,
    current_user,
    round_index: int,
):
    data = await request.json()
    correct_count = int(data.get("correct_count") or 0)
    wrong_count = int(data.get("wrong_count") or 0)
    avg_time_ms = float(data.get("avg_time_ms") or 0)
    min_time_ms = float(data.get("min_time_ms") or 0)
    total_questions = int(data.get("total_questions") or 0)
    per_question = data.get("per_question") or []

    if correct_count < 0 or wrong_count < 0:
        raise HTTPException(status_code=422, detail="Counts must be non-negative")
    if correct_count > 200 or wrong_count > 200 or total_questions > 300:
        raise HTTPException(status_code=422, detail="Counts too large")
    if (correct_count + wrong_count) and total_questions and total_questions != (
        correct_count + wrong_count
    ):
        raise HTTPException(status_code=422, detail="Total questions mismatch")
    if len(per_question) > 400:
        raise HTTPException(status_code=422, detail="Too many per-question entries")

    is_valid = not (min_time_ms < 150)
    enforce_range(avg_time_ms, 0, 10000, "Average time")
    enforce_range(min_time_ms, 50, 5000, "Minimum time")

    score_value = calculate_arithmetic_score(
        correct_count, wrong_count, avg_time_ms, per_question
    )

    enforce_range(score_value, -2000, 50000, "Score")

    raw_payload = data.copy()
    raw_payload.update(
        {"score": score_value, "is_valid": is_valid, "round_index": round_index}
    )

    score_key = "round2_score" if round_index == 2 else "round3_score"
    response_payload = {
        "status": "success",
        score_key: score_value,
        "is_valid": is_valid,
        "per_question": per_question,
    }

    if not current_user:
        response_payload["round_mixed_score_id"] = None
        response_payload["message"] = f"Login to save your Round {round_index} score"
        return response_payload

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO math_round_mixed_scores (
                    user_id, score, correct_count, wrong_count,
                    avg_time_ms, min_time_ms, total_questions, is_valid, raw_payload, round_index, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id, created_at
                """,
                (
                    current_user["id"],
                    score_value,
                    correct_count,
                    wrong_count,
                    avg_time_ms,
                    min_time_ms,
                    total_questions,
                    is_valid,
                    psycopg2.extras.Json(raw_payload),
                    round_index,
                ),
            )
            inserted = cursor.fetchone()
            new_id = inserted[0]
        check_and_award_achievements(
            conn,
            current_user["id"],
            "math_round2" if round_index == 2 else "math_round3",
            {
                "avg_time_ms": avg_time_ms,
                "wrong_count": wrong_count,
                "correct_count": correct_count,
                "created_at": inserted[1] if inserted else None,
            },
        )
        conn.commit()
    finally:
        conn.close()

    response_payload["round_mixed_score_id"] = new_id
    return response_payload


async def save_round2_score(request: Request, current_user):
    return await _save_round_mixed_score(request, current_user, 2)


async def save_round3_score(request: Request, current_user):
    return await _save_round_mixed_score(request, current_user, 3)


@router.post("/api/math-game/round1/submit")
async def submit_round1_score(
    request: Request,
    current_user=Depends(get_current_user),
    _=Depends(csrf_protected),
):
    return await save_round1_score(request, current_user)


@router.post("/api/math-game/round2/submit")
async def submit_round2_score_endpoint(
    request: Request,
    current_user=Depends(get_current_user),
    _=Depends(csrf_protected),
):
    response = await save_round2_score(request, current_user)
    return JSONResponse(content=response)


@router.post("/api/math-game/round3/submit")
async def submit_round3_score_endpoint(
    request: Request,
    current_user=Depends(get_current_user),
    _=Depends(csrf_protected),
):
    response = await save_round3_score(request, current_user)
    return JSONResponse(content=response)


@router.post("/api/math-game/session/submit")
async def submit_math_session(
    request: Request,
    current_user=Depends(get_current_user),
    _=Depends(csrf_protected),
):
    data = await request.json()
    round1_score_id = int(data.get("round1_score_id") or 0)
    round2_score_id = int(data.get("round2_score_id") or 0)
    round3_score_id = int(data.get("round3_score_id") or 0)
    combined_score = int(data.get("combined_score") or 0)

    if not (round1_score_id and round2_score_id and round3_score_id):
        raise HTTPException(status_code=400, detail="Round IDs required")
    if combined_score < 0 or combined_score > 200000:
        raise HTTPException(status_code=422, detail="Combined score out of range")

    if not current_user:
        return JSONResponse(
            content={
                "status": "success",
                "message": "Login to save your math session",
                "combined_score": combined_score,
            }
        )

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO math_session_scores (
                    user_id, round1_score_id, round2_score_id, round3_score_id, combined_score
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    current_user["id"],
                    round1_score_id,
                    round2_score_id,
                    round3_score_id or None,
                    combined_score,
                ),
            )
            inserted = cursor.fetchone()
            new_id = inserted[0]
        check_and_award_achievements(
            conn,
            current_user["id"],
            "math_session",
            {
                "combined_score": combined_score,
                "created_at": inserted[1] if inserted else None,
            },
        )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(content={"status": "success", "session_id": new_id})


@router.get("/api/math-game/round1/leaderboard")
async def round1_leaderboard_api(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Sign in required")

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    u.username,
                    s.score,
                    s.correct_count,
                    s.wrong_count,
                    s.avg_time_ms,
                    s.created_at
                FROM math_round1_scores s
                JOIN users u ON u.id = s.user_id
                WHERE s.is_valid = TRUE
                ORDER BY s.score DESC, s.created_at ASC
                LIMIT 20
                """
            )
            rows = cursor.fetchall()
        scores = []
        for row in rows:
            avg_time_raw = row.get("avg_time_ms")
            scores.append(
                {
                    "username": row["username"],
                    "score": int(row["score"]),
                    "correct_count": int(row["correct_count"]),
                    "wrong_count": int(row["wrong_count"]),
                    "avg_time_ms": float(avg_time_raw)
                    if avg_time_raw is not None
                    else None,
                    "created_at": row["created_at"].isoformat(),
                }
            )
        return JSONResponse(content={"scores": scores})
    finally:
        conn.close()


@router.get("/api/math-game/round-mixed/leaderboard")
async def mixed_round_leaderboard_api(
    request: Request,
    current_user=Depends(get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Sign in required")

    round_index_param = request.query_params.get("round_index")
    try:
        round_index = int(round_index_param) if round_index_param else None
    except ValueError:
        round_index = None

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    u.username,
                    s.score,
                    s.correct_count,
                    s.wrong_count,
                    s.avg_time_ms,
                    s.created_at
                FROM math_round_mixed_scores s
                JOIN users u ON u.id = s.user_id
                WHERE s.is_valid = TRUE
                  AND (%s IS NULL OR s.round_index = %s OR (s.round_index IS NULL AND %s = 2))
                ORDER BY s.score DESC, s.created_at ASC
                LIMIT 20
                """,
                (round_index, round_index, round_index),
            )
            rows = cursor.fetchall()
        scores = []
        for row in rows:
            avg_time_raw = row.get("avg_time_ms")
            scores.append(
                {
                    "username": row["username"],
                    "score": int(row["score"]),
                    "correct_count": int(row["correct_count"]),
                    "wrong_count": int(row["wrong_count"]),
                    "avg_time_ms": float(avg_time_raw)
                    if avg_time_raw is not None
                    else None,
                    "created_at": row["created_at"].isoformat(),
                }
            )
        return JSONResponse(content={"scores": scores})
    finally:
        conn.close()


@router.get("/api/math-game/score-distribution")
async def math_score_distribution():
    bucket_width = 20
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT FLOOR(score::numeric / %s) AS bucket, COUNT(*)
                FROM math_round1_scores
                WHERE is_valid = TRUE
                GROUP BY bucket
                ORDER BY bucket
                """,
                (bucket_width,),
            )
            rows = cursor.fetchall()
        buckets = []
        for bucket, count in rows:
            min_val = int(bucket) * bucket_width
            max_val = min_val + bucket_width - 1
            buckets.append({"min": min_val, "max": max_val, "count": count})
        return JSONResponse(content={"buckets": buckets})
    finally:
        conn.close()


@router.get("/api/math-game/difficulty-summary")
async def math_difficulty_summary():
    # Placeholder; you can fill this later with real hardest/easiest logic
    return JSONResponse(content={"hardest_questions": [], "easiest_questions": []})
