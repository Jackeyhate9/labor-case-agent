"""Link extracted facts to exact timestamped audio segments."""

import sqlalchemy as sa
from alembic import op


revision = "0005_audio_fact_provenance"
down_revision = "0004_versioned_embeddings"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("facts")}
    if "source_audio_segment_id" not in columns:
        with op.batch_alter_table("facts") as batch:
            batch.add_column(sa.Column("source_audio_segment_id", sa.String(36), nullable=True))
            batch.create_foreign_key(
                "fk_facts_source_audio_segment_id",
                "audio_segments",
                ["source_audio_segment_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("facts")}
    if "source_audio_segment_id" in columns:
        with op.batch_alter_table("facts") as batch:
            batch.drop_constraint("fk_facts_source_audio_segment_id", type_="foreignkey")
            batch.drop_column("source_audio_segment_id")
