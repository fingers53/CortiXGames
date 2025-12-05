import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIRS = [BASE_DIR / "templates", BASE_DIR / "math-games" / "templates"]
STATIC_DIR = BASE_DIR / "static"
MATH_STATIC_DIR = BASE_DIR / "math-games" / "static"

DATABASE_URL = os.getenv("DATABASE_URL")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE_NAME = "session_user_id"
SESSION_MAX_AGE_SHORT = 60 * 60 * 12
SESSION_MAX_AGE_LONG = 60 * 60 * 24 * 30
