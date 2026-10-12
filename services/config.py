"""Central configuration. Everything comes from environment variables / .env."""
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()  # also honour a .env in the current directory


def _env(name, default=""):
    return (os.getenv(name) or default).strip()


def _int(name, default):
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _list(name, default=""):
    return [x.strip() for x in _env(name, default).split(",") if x.strip()]


def _pick_db_path():
    wanted = Path(_env("DB_PATH") or (BASE_DIR / "data" / "research_platform.db"))
    try:
        wanted.parent.mkdir(parents=True, exist_ok=True)
        probe = wanted.parent / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        return wanted
    except OSError:
        return Path(tempfile.gettempdir()) / "research_platform.db"


# ---- AI providers -------------------------------------------------------
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODELS = _list("GEMINI_MODELS", "gemini-3.8-flash,gemini-2.5-flash,gemini-2.5-flash-lite")
GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENROUTER_API_KEY = _env("OPENROUTER_API_KEY")
OPENROUTER_MODEL = _env("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

# ---- Paper sources ------------------------------------------------------
SERPAPI_KEY = _env("SERPAPI_KEY")
CONTACT_EMAIL = _env("CONTACT_EMAIL")
S2_API_KEY = _env("S2_API_KEY")
OPENALEX_API_KEY = _env("OPENALEX_API_KEY")

# ---- Storage ------------------------------------------------------------
DB_PATH = _pick_db_path()

# ---- Monetisation -------------------------------------------------------
LICENSE_SECRET = _env("LICENSE_SECRET")
MONETIZATION_ENABLED = bool(LICENSE_SECRET)
PAYMENT_LINK = _env("PAYMENT_LINK")
PRO_PRICE_TEXT = _env("PRO_PRICE_TEXT", "Rs 199 / month")
LICENSE_REVOKED = {k.upper() for k in _list("LICENSE_REVOKED")}

FREE_AI_PER_DAY = _int("FREE_AI_PER_DAY", 5)
GLOBAL_AI_PER_DAY = _int("GLOBAL_AI_PER_DAY", 0)

FREE_COMPARE_MAX = 3
PRO_COMPARE_MAX = 5
FREE_WORKSPACES = 3
FREE_PAPERS_PER_WORKSPACE = 30
UNLIMITED = 10 ** 6
