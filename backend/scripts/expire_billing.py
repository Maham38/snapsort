"""Expire event plans and flag data that needs retention review.

This command intentionally never deletes event data. Review flagged events
before applying any retention policy.
"""

from app.billing import expire_plans_and_flag_retention
from app.db import SessionLocal


def main() -> None:
    with SessionLocal() as db:
        expired = expire_plans_and_flag_retention(db)
    print(f"Expired {expired} event plan(s); retention flags were updated.")


if __name__ == "__main__":
    main()
