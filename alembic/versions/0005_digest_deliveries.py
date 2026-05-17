"""add digest deliveries

Revision ID: 0005_digest_deliveries
Revises: 0004_article_source_category
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_digest_deliveries"
down_revision = "0004_article_source_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    delivery_status = sa.Enum("PENDING", "SENT", "FAILED", name="digestdeliverystatus")
    delivery_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "digest_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("digest_id", sa.Integer(), sa.ForeignKey("digests.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False, server_default="email"),
        sa.Column("provider", sa.String(length=100), nullable=False, server_default="local"),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("status", delivery_status, nullable=False, server_default="PENDING"),
        sa.Column("feedback_token", sa.String(length=255), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_digest_deliveries_digest_id", "digest_deliveries", ["digest_id"])


def downgrade() -> None:
    op.drop_index("ix_digest_deliveries_digest_id", table_name="digest_deliveries")
    op.drop_table("digest_deliveries")
    sa.Enum("PENDING", "SENT", "FAILED", name="digestdeliverystatus").drop(op.get_bind(), checkfirst=True)
