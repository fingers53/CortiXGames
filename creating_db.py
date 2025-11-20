import sqlite3
from datetime import datetime


def ensure_column(conn, table_name: str, column_name: str, definition: str):
    """Add a column to a table if it doesn't already exist."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {col[1] for col in cursor.fetchall()}
    if column_name not in existing_columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def initialize_db():
    conn = sqlite3.connect("scores.sqlite3")
    cursor = conn.cursor()

    # Create users table with country tracking
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            last_country TEXT
        )
        """
    )

    # Backfill missing user columns for older databases
    ensure_column(conn, "users", "created_at", "TEXT")
    ensure_column(conn, "users", "last_country", "TEXT")
    ensure_column(conn, "users", "ip_address", "TEXT")

    # Create reaction_scores table with detailed timing
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reaction_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            final_score REAL NOT NULL,
            average_time_ms REAL NOT NULL,
            fastest_time_ms REAL NOT NULL,
            slowest_time_ms REAL NOT NULL,
            accuracy REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # Ensure legacy columns are present for compatibility
    ensure_column(conn, "reaction_scores", "score", "INTEGER")
    ensure_column(conn, "reaction_scores", "avg_reaction_time", "REAL")
    ensure_column(conn, "reaction_scores", "final_score", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "reaction_scores", "average_time_ms", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "reaction_scores", "fastest_time_ms", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "reaction_scores", "slowest_time_ms", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "reaction_scores", "accuracy", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "reaction_scores", "created_at", "TEXT NOT NULL DEFAULT ''")

    # Create memory_scores table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            score INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    ensure_column(conn, "memory_scores", "avg_reaction_time", "REAL")
    ensure_column(conn, "memory_scores", "created_at", "TEXT NOT NULL DEFAULT ''")

    conn.commit()
    conn.close()
    print(f"Database initialized successfully at {datetime.utcnow().isoformat()}.")


if __name__ == "__main__":
    initialize_db()
