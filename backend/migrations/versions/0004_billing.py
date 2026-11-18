"""Add organizer pay-per-event billing and usage quotas."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_billing"
down_revision = "0003_security_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for enum_name, values in (
        ("plan_tier", ("free_trial", "standard", "pro", "enterprise")),
        ("plan_status", ("trial", "active", "expired")),
        ("payment_status", ("pending", "paid", "failed")),
    ):
        sa.Enum(*values, name=enum_name).create(bind, checkfirst=True)

    op.create_table(
        "plans",
        sa.Column(
            "tier",
            postgresql.ENUM(
                "free_trial", "standard", "pro", "enterprise",
                name="plan_tier", create_type=False
            ),
            primary_key=True,
        ),
        sa.Column("max_photos", sa.Integer(), nullable=False),
        sa.Column("max_storage_bytes", sa.BigInteger(), nullable=False),
        sa.Column("max_matching_searches", sa.Integer(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.bulk_insert(
        sa.table(
            "plans",
            sa.column("tier", sa.String()),
            sa.column("max_photos", sa.Integer()),
            sa.column("max_storage_bytes", sa.BigInteger()),
            sa.column("max_matching_searches", sa.Integer()),
            sa.column("retention_days", sa.Integer()),
            sa.column("price_cents", sa.Integer()),
            sa.column("currency", sa.String()),
            sa.column("active", sa.Boolean()),
        ),
        [
            {"tier": "free_trial", "max_photos": 100, "max_storage_bytes": 1073741824,
             "max_matching_searches": 25, "retention_days": 30, "price_cents": 0,
             "currency": "usd", "active": True},
            {"tier": "standard", "max_photos": 5000, "max_storage_bytes": 26843545600,
             "max_matching_searches": 500, "retention_days": 90, "price_cents": 4900,
             "currency": "usd", "active": True},
            {"tier": "pro", "max_photos": 25000, "max_storage_bytes": 107374182400,
             "max_matching_searches": 2500, "retention_days": 180, "price_cents": 14900,
             "currency": "usd", "active": True},
            {"tier": "enterprise", "max_photos": 1000000, "max_storage_bytes": 1099511627776,
             "max_matching_searches": 100000, "retention_days": 365, "price_cents": 0,
             "currency": "usd", "active": True},
        ],
    )

    op.add_column(
        "events",
        sa.Column(
            "plan_tier",
            postgresql.ENUM(
                "free_trial", "standard", "pro", "enterprise",
                name="plan_tier", create_type=False
            ),
        ),
    )
    op.add_column(
        "events",
        sa.Column(
            "plan_status",
            postgresql.ENUM(
                "trial", "active", "expired",
                name="plan_status", create_type=False
            ),
            nullable=False,
            server_default="expired",
        ),
    )
    op.add_column("events", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column(
        "events",
        sa.Column(
            "retention_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "photos",
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "photos",
        sa.Column(
            "usage_counted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_table(
        "event_usage",
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), primary_key=True),
        sa.Column("photo_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("matching_searches", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("organizer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_ref", sa.String(255), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "paid", "failed",
                name="payment_status", create_type=False
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider_ref"),
    )
    op.create_index("ix_payments_event_id", "payments", ["event_id"])
    op.create_index("ix_payments_organizer_id", "payments", ["organizer_id"])

    # Existing events receive one migration-safe trial per organizer. Other
    # existing events require an explicit paid plan.
    op.execute(
        """
        WITH ranked AS (
            SELECT id, organizer_id,
                   row_number() OVER (PARTITION BY organizer_id ORDER BY created_at, id) AS rank
            FROM events
        )
        UPDATE events
        SET plan_tier = CASE WHEN ranked.rank = 1 THEN 'free_trial'::plan_tier ELSE NULL END,
            plan_status = CASE WHEN ranked.rank = 1 THEN 'trial'::plan_status ELSE 'expired'::plan_status END,
            expires_at = CASE WHEN ranked.rank = 1 THEN events.created_at + interval '30 days' ELSE NULL END
        FROM ranked
        WHERE events.id = ranked.id
        """
    )
    op.execute("INSERT INTO event_usage (event_id) SELECT id FROM events")
    op.alter_column("events", "plan_status", server_default=None)
    op.alter_column("events", "retention_review_required", server_default=None)
    op.alter_column("photos", "size_bytes", server_default=None)
    op.alter_column("photos", "usage_counted", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_payments_organizer_id", table_name="payments")
    op.drop_index("ix_payments_event_id", table_name="payments")
    op.drop_table("payments")
    op.drop_table("event_usage")
    op.drop_column("photos", "usage_counted")
    op.drop_column("photos", "size_bytes")
    op.drop_column("events", "retention_review_required")
    op.drop_column("events", "expires_at")
    op.drop_column("events", "plan_status")
    op.drop_column("events", "plan_tier")
    op.drop_table("plans")
    for enum_name in ("payment_status", "plan_status", "plan_tier"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
