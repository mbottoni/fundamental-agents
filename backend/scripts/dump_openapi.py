"""
Write the OpenAPI document to a file.

Used to generate the frontend's TypeScript types (`npm run gen:types`) and by
the CI check that fails when the two have drifted. Importing the app is enough
— no server, no database, no provider keys beyond the placeholders below.
"""

import json
import os
import sys
from pathlib import Path

# config.py has no defaults for these and raises at import time, which would
# otherwise make generating a schema require a full environment.
_PLACEHOLDERS = {
    "SECRET_KEY": "openapi-dump-placeholder-key-at-least-32-chars",
    "DATABASE_URL": "sqlite:///./openapi-dump.db",
    "FINANCIAL_MODELING_PREP_API_KEY": "unused",
    "NEWS_API_KEY": "unused",
    "STRIPE_SECRET_KEY": "unused",
    "STRIPE_WEBHOOK_SECRET": "unused",
}
for key, value in _PLACEHOLDERS.items():
    os.environ.setdefault(key, value)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

if __name__ == "__main__":
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    destination.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"Wrote {destination}")
