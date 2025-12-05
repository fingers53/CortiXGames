import psycopg2
from .config import DATABASE_URL


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def ensure_yetamax_scores_table():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS yetamax_scores (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    score INTEGER NOT NULL,
                    correct_count INTEGER NOT NULL,
                    wrong_count INTEGER NOT NULL,
                    avg_time_ms DOUBLE PRECISION NOT NULL,
                    min_time_ms DOUBLE PRECISION NOT NULL,
                    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
                    raw_payload JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_yetamax_scores_score_created_at
                ON yetamax_scores (score DESC, created_at ASC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_yetamax_scores_user_recent
                ON yetamax_scores (user_id, created_at DESC)
                """
            )
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'math_scores'
                )
                """
            )
            old_table_exists = cursor.fetchone()[0]

            if old_table_exists:
                cursor.execute("SELECT COUNT(*) FROM yetamax_scores")
                new_count = cursor.fetchone()[0]
                if new_count == 0:
                    cursor.execute(
                        """
                        INSERT INTO yetamax_scores (
                            user_id, score, correct_count, wrong_count,
                            avg_time_ms, min_time_ms, is_valid, raw_payload, created_at
                        )
                        SELECT user_id, score, correct_count, wrong_count,
                               avg_time_ms, min_time_ms, is_valid, raw_payload, created_at
                        FROM math_scores
                        """
                    )
        conn.commit()
    finally:
        conn.close()


def ensure_maveric_scores_table():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS maveric_scores (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    score INTEGER NOT NULL,
                    correct_count INTEGER NOT NULL,
                    wrong_count INTEGER NOT NULL,
                    avg_time_ms DOUBLE PRECISION NOT NULL,
                    min_time_ms DOUBLE PRECISION NOT NULL,
                    total_questions INTEGER NOT NULL,
                    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
                    raw_payload JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_maveric_scores_score_created_at
                ON maveric_scores (score DESC, created_at ASC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_maveric_scores_user_recent
                ON maveric_scores (user_id, created_at DESC)
                """
            )
        conn.commit()
    finally:
        conn.close()


def ensure_math_session_scores_table():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS math_session_scores (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    round1_score_id INTEGER NOT NULL REFERENCES yetamax_scores(id),
                    round2_score_id INTEGER NOT NULL REFERENCES maveric_scores(id),
                    combined_score INTEGER NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_math_sessions_user_recent
                ON math_session_scores (user_id, created_at DESC)
                """
            )
        conn.commit()
    finally:
        conn.close()
