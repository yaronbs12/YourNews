"""enforce unique article source urls

Revision ID: 0003_article_sources_unique_url
Revises: 0002_article_source_rss_fields
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_article_sources_unique_url"
down_revision = "0002_article_source_rss_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Re-point article foreign keys to the kept source row (lowest id per duplicated URL).
    op.execute(
        """
        UPDATE articles AS a
        SET source_id = keep.keep_id
        FROM (
            SELECT dup.id AS dup_id, kept.keep_id
            FROM article_sources AS dup
            JOIN (
                SELECT url, MIN(id) AS keep_id
                FROM article_sources
                GROUP BY url
                HAVING COUNT(*) > 1
            ) AS kept ON kept.url = dup.url
            WHERE dup.id <> kept.keep_id
        ) AS keep
        WHERE a.source_id = keep.dup_id
        """
    )

    # Remove duplicated source rows after articles now point at the kept row.
    op.execute(
        """
        DELETE FROM article_sources AS src
        USING (
            SELECT dup.id AS dup_id
            FROM article_sources AS dup
            JOIN (
                SELECT url, MIN(id) AS keep_id
                FROM article_sources
                GROUP BY url
                HAVING COUNT(*) > 1
            ) AS kept ON kept.url = dup.url
            WHERE dup.id <> kept.keep_id
        ) AS duplicates
        WHERE src.id = duplicates.dup_id
        """
    )

    # Enforce one source row per URL.
    op.create_unique_constraint("uq_article_sources_url", "article_sources", ["url"])


def downgrade() -> None:
    op.drop_constraint("uq_article_sources_url", "article_sources", type_="unique")
