"""Add match result persistence and vector search index."""

from alembic import op
import sqlalchemy as sa

revision = "0002_matching_results"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("matching_job_id", sa.String(36), sa.ForeignKey("matching_jobs.id"), nullable=False),
        sa.Column("photo_id", sa.String(36), sa.ForeignKey("photos.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("matching_job_id", "photo_id"),
    )
    op.create_index(
        "ix_face_embeddings_event_embedding",
        "face_embeddings",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_face_embeddings_event_embedding", table_name="face_embeddings")
    op.drop_table("match_results")
