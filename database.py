# database.py
# Supabase client for Traffic-Predictor FastAPI
# Pairs with main.py

# Uses the same .env as load_data_to_supabase.py: SUPABASE_URL and SUPABASE_KEY.
# No DATABASE_URL or Postgres password needed; the API talks to Supabase over HTTP.

# 0. Setup #################################

import os
from pathlib import Path
from typing import Optional
from supabase import create_client, Client

## 0.1 Load .env ###############################

_script_dir = Path(__file__).resolve().parent
_env_path = _script_dir / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)

## 0.2 Supabase client ###############################

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABSE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Set SUPABASE_URL and SUPABASE_KEY (or SUPABSE_SERVICE_ROLE_KEY) in .env. "
        "See SUPABASE_SETUP.md."
    )

_client: Optional[Client] = None


def get_supabase() -> Client:
    """Return the Supabase client (singleton). Use in FastAPI via Depends(get_supabase)."""
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client
