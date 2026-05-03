"""add article source rss fields

Revision ID: 0002_article_source_rss_fields
Revises: 0001_initial_schema
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_article_source_rss_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("article_sources", sa.Column("source_type", sa.String(length=50), nullable=False, server_default="rss"))
    op.add_column("article_sources", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("article_sources", sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("article_sources", "last_fetched_at")
    op.drop_column("article_sources", "enabled")
    op.drop_column("article_sources", "source_type")
