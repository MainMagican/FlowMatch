"""Application configuration for the FlowMatch backend.

Kept intentionally small: everything is read from environment variables with
safe defaults so the app runs out of the box in a local/demo environment with
no external credentials (per docs/DECISIONS.md #2, #3, #4).
"""

import os

# Secret used to sign dev-mode bearer tokens. In a real deployment this would
# be replaced by a real identity provider (Entra ID) - see app/auth.py.
TOKEN_SIGNING_SECRET = os.environ.get("FLOWMATCH_TOKEN_SECRET", "dev-only-not-for-production-flowmatch")

TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

DB_PATH = os.environ.get(
    "FLOWMATCH_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flowmatch.db"),
)
