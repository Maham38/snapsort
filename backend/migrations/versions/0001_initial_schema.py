"""Create Phase 3 SnapSort schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for enum_name, values in (
        ("user_role", ("organizer", "photographer", "attendee")),
        ("event_status", ("draft", "active", "archived")),
        ("processing_status", ("pending", "processing", "complete", "failed")),
        ("matching_status", ("pending", "processing", "complete", "failed")),
        ("consent_type", ("face_matching",)),
    ):
        sa.Enum(*values, name=enum_name).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("role", postgresql.ENUM("organizer", "photographer", "attendee", name="user_role", create_type=False)),        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organizer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("event_code", sa.String(12), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "active", "archived", name="event_status", create_type=False), nullable=False),        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_code"),
    )
    op.create_index("ix_events_organizer_id", "events", ["organizer_id"])
    op.create_index("ix_events_event_code", "events", ["event_code"])
    op.create_table(
        "event_participants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_id", "user_id"),
    )
    op.create_table(
        "photographer_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("photographer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_id", "photographer_id"),
    )
    op.create_table(
        "photos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("checksum", sa.String(128)),
        sa.Column("processing_status", postgresql.ENUM("pending", "processing", "complete", "failed", name="processing_status", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_table(
        "face_embeddings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("photo_id", sa.String(36), sa.ForeignKey("photos.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("embedding", Vector(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "matching_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("attendee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("selfie_storage_key", sa.String(500), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "processing", "complete", "failed", name="matching_status", create_type=False), nullable=False),        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "favorites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("photo_id", sa.String(36), sa.ForeignKey("photos.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "photo_id"),
    )
    op.create_table(
        "consent_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("consent_type", postgresql.ENUM("face_matching", name="consent_type", create_type=False), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "consent_records",
        "favorites",
        "matching_jobs",
        "face_embeddings",
        "photos",
        "photographer_assignments",
        "event_participants",
        "events",
        "users",
    ):
        op.drop_table(table)
    for enum_name in ("consent_type", "matching_status", "processing_status", "event_status", "user_role"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS vector")
