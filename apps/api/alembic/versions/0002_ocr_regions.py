"""Add explicit OCR region coordinates without removing the v0.1 JSON box."""

import sqlalchemy as sa
from alembic import op


revision = "0002_ocr_regions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("evidence_regions")}
    additions = {
        "bbox_x": sa.Column("bbox_x", sa.Numeric(12, 4), nullable=True),
        "bbox_y": sa.Column("bbox_y", sa.Numeric(12, 4), nullable=True),
        "bbox_width": sa.Column("bbox_width", sa.Numeric(12, 4), nullable=True),
        "bbox_height": sa.Column("bbox_height", sa.Numeric(12, 4), nullable=True),
        "created_at": sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    }
    with op.batch_alter_table("evidence_regions") as batch:
        for name, column in additions.items():
            if name not in columns:
                batch.add_column(column)


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("evidence_regions")}
    with op.batch_alter_table("evidence_regions") as batch:
        for name in ("created_at", "bbox_height", "bbox_width", "bbox_y", "bbox_x"):
            if name in columns:
                batch.drop_column(name)
