"""add article source category

Revision ID: 0004_article_source_category
Revises: 0003_article_sources_unique_url
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_article_source_category"
down_revision = "0003_article_sources_unique_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "article_sources",
        sa.Column("category", sa.String(length=100), nullable=False, server_default="general"),
    )


def downgrade() -> None:
    op.drop_column("article_sources", "category")
