"""Harden consent uniqueness."""

from alembic import op

revision = "0003_security_hardening"
down_revision = "0002_matching_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM consent_records older
        USING consent_records newer
        WHERE older.user_id = newer.user_id
          AND older.event_id = newer.event_id
          AND older.consent_type = newer.consent_type
          AND older.created_at < newer.created_at
        """
    )
    op.create_index(
        "ix_consent_records_user_event_type",
        "consent_records",
        ["user_id", "event_id", "consent_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_consent_records_user_event_type",
        table_name="consent_records",
    )
