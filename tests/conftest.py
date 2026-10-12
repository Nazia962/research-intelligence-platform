import os
import sys
import tempfile
from pathlib import Path

# Use a throw-away database and no real API keys during tests.
_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = str(Path(_tmp) / "test.db")
for var in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "SERPAPI_KEY", "LICENSE_SECRET"):
    os.environ[var] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
