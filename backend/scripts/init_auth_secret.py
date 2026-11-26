"""Generate a local JWT secret without printing it or replacing an existing key."""

import secrets
from pathlib import Path

from dotenv import dotenv_values

backend = Path(__file__).resolve().parents[1]
path = backend / ".env"
if not path.exists():
    path.write_text((backend / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
existing = dotenv_values(path).get("JWT_SECRET")
if existing:
    if len(existing) < 32:
        raise SystemExit(
            "Existing JWT_SECRET is too short; update it locally (at least 32 characters)."
        )
    print("Existing JWT_SECRET preserved.")
else:
    content = path.read_text(encoding="utf-8")
    lines = [line for line in content.splitlines() if not line.strip().startswith("JWT_SECRET=")]
    lines.append("JWT_SECRET=" + secrets.token_urlsafe(48))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("JWT_SECRET generated in backend/.env; secret not displayed.")
