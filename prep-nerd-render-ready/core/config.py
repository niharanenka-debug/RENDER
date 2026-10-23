import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]


DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "instance" / "prep_nerd.db")))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
LOCAL_DEMO = os.getenv("PREP_NERD_LOCAL_DEMO", "false").strip().lower() in {"1", "true", "yes"}
QUESTION_COUNTS = (5, 10, 15, 20, 25)
DIFFICULTIES = ("Easy", "Medium", "Hard")
ANALYSIS_DEPTHS = ("Automatic", "Quick", "Standard", "Deep", "Exhaustive")
SUMMARY_STYLES = ("Executive Summary", "Key Takeaways", "Detailed Analysis", "Short Abstract", "Action Items")
SUMMARY_LENGTHS = ("Very Short", "Medium", "Comprehensive")
MAX_QUESTIONS = 25


def api_key():
    return os.getenv("GEMINI_API_KEY") or None
