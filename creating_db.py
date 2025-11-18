import sqlite3

def initialize_db():
    conn = sqlite3.connect("scores.sqlite3")
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        ip_address TEXT
    )
    """)

    # Create reaction_scores table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reaction_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        avg_reaction_time REAL,
        accuracy REAL
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Create memory_scores table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memory_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        avg_reaction_time REAL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

# Run the function to initialize the database
initialize_db()
