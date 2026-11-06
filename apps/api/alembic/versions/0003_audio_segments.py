"""Add timestamped speaker-aware audio segments."""

import sqlalchemy as sa
from alembic import op


revision = "0003_audio_segments"
down_revision = "0002_ocr_regions"
branch_labels = None
depends_on = None


def upgrade():
    if "audio_segments" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "audio_segments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False),
        sa.Column("speaker_id", sa.String(30), nullable=False),
        sa.Column("start_time", sa.Numeric(12, 3), nullable=False),
        sa.Column("end_time", sa.Numeric(12, 3), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
    )
    op.create_index("ix_audio_segments_evidence_id", "audio_segments", ["evidence_id"])


def downgrade():
    if "audio_segments" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("audio_segments")
