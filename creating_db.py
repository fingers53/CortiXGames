import sqlite3
from datetime import datetime


def initialize_db():
    conn = sqlite3.connect("scores.sqlite3")
    cursor = conn.cursor()

    # Fresh user table keyed by username with optional country tracking.
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            country_code TEXT
        )
        """
    )

    # Reaction scores capture timing stats and a final score value.
    cursor.execute("DROP TABLE IF EXISTS reaction_scores")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reaction_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            score REAL NOT NULL,
            average_time_ms REAL NOT NULL,
            fastest_time_ms REAL NOT NULL,
            slowest_time_ms REAL NOT NULL,
            accuracy REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    # Memory scores now store per-round and total values.
    cursor.execute("DROP TABLE IF EXISTS memory_scores")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_score REAL NOT NULL,
            round1_score REAL,
            round2_score REAL,
            round3_score REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()
    conn.close()
    print(f"Database initialized successfully at {datetime.utcnow().isoformat()}.")


if __name__ == "__main__":
    initialize_db()
