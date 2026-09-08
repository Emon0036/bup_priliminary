import os
from pathlib import Path
from dotenv import load_dotenv

# Local development may use an ignored .env file; Vercel provides these as
# environment variables, which take precedence over file values.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "")
APP_VERSION = "1.0.0"
MAX_MONTHS = 24
MAX_CSP_BATCH = 30
