"""Add versioned embedding storage without invalidating old cases."""

import sqlalchemy as sa
from alembic import op


revision = "0004_versioned_embeddings"
down_revision = "0003_audio_segments"
branch_labels = None
depends_on = None


def upgrade():
    if "evidence_embeddings" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "evidence_embeddings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("embedding_model_version", sa.String(80), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("case_id", "entity_type", "entity_id", "embedding_model_version"):
        op.create_index(f"ix_evidence_embeddings_{column}", "evidence_embeddings", [column])


def downgrade():
    if "evidence_embeddings" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("evidence_embeddings")
