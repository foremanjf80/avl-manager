"""Settings for the Airtable backend.

Read at call time rather than import time so the CLI can load a .env, and so
tests can flip a variable without re-importing the package.
"""
import os

# Which store the app reads and writes. "sqlite" is the live backend today;
# "airtable" is reserved for the cutover and is rejected until the data layer
# is switched over, so a half-set .env can never silently point at nothing.
BACKENDS = ("sqlite", "airtable")

API_URL = "https://api.airtable.com/v0"
META_URL = "https://api.airtable.com/v0/meta"

# Airtable enforces 5 requests/second per base and answers a 6th with 429 plus a
# 30-second lockout. Stay just under it rather than relying on retries.
DEFAULT_RATE_LIMIT = 4.0
MAX_BATCH = 10          # records per create/update/delete call
MAX_PAGE = 100          # records per list page

def _env(name, default=""):
    return (os.environ.get(name) or default).strip()

def backend():
    b = _env("AVL_BACKEND", "sqlite").lower()
    return b if b in BACKENDS else "sqlite"

def pat():
    return _env("AIRTABLE_PAT")

def base_id():
    return _env("AIRTABLE_BASE_ID")

def workspace_id():
    return _env("AIRTABLE_WORKSPACE_ID")

def rate_limit():
    try:
        return float(_env("AIRTABLE_RATE_LIMIT") or DEFAULT_RATE_LIMIT)
    except ValueError:
        return DEFAULT_RATE_LIMIT

def timeout():
    try:
        return float(_env("AIRTABLE_TIMEOUT") or 30.0)
    except ValueError:
        return 30.0

def require(*names):
    """Fail loudly and specifically instead of sending an unauthenticated call."""
    missing = [n for n in names if not _env(n)]
    if missing:
        raise RuntimeError(
            "Missing Airtable settings: " + ", ".join(missing) +
            ". Copy .env.example to .env and fill them in (see README > Airtable).")
