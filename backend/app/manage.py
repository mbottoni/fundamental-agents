"""
Things an operator does by hand, on the server.

    python -m app.manage verify <email>     mark an account's address as verified
    python -m app.manage users              list accounts

In production, with docker compose:

    docker compose -f docker-compose.prod.yml --env-file .env.prod \
        exec api python -m app.manage verify you@example.com

`verify` exists because verification is by emailed link, and a deployment may
not have email configured yet. The alternative, reading the link out of the
log, means writing working tokens to the log; production does not do that.
"""

import sys

from . import crud
from .core.db import SessionLocal
from .db import base as _models  # noqa: F401 - registers every model
from .models.user import User

USAGE = "usage: python -m app.manage verify <email> | users"


def verify(email: str) -> int:
    db = SessionLocal()
    try:
        user = crud.get_user_by_email(db, email=email)
        if user is None:
            print(f"No account with the address {email!r}.")
            return 1
        if user.is_verified:
            print(f"{email} was already verified.")
            return 0
        user.is_verified = True
        db.commit()
        print(f"{email} is now verified.")
        return 0
    finally:
        db.close()


def users() -> int:
    db = SessionLocal()
    try:
        rows = db.query(User).order_by(User.id).all()
        for user in rows:
            print(
                f"{user.id}\t{user.email}\t"
                f"{'verified' if user.is_verified else 'unverified'}\t"
                f"{user.subscription_status or 'free'}"
            )
        print(f"{len(rows)} account(s)")
        return 0
    finally:
        db.close()


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "verify":
        return verify(argv[1])
    if argv == ["users"]:
        return users()
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
