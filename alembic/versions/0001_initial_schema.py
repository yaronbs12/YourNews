"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("article_sources", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(length=255), nullable=False, unique=True), sa.Column("url", sa.String(length=1024), nullable=False))
    op.create_table("topics", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(length=100), nullable=False, unique=True))
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(length=255), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table("articles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("source_id", sa.Integer(), sa.ForeignKey("article_sources.id"), nullable=False), sa.Column("title", sa.String(length=500), nullable=False), sa.Column("url", sa.String(length=1024), nullable=False, unique=True), sa.Column("content", sa.Text(), nullable=True), sa.Column("published_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    op.create_table("article_topics", sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), primary_key=True), sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), primary_key=True), sa.Column("relevance_score", sa.Integer(), nullable=False, server_default="1"))
    op.create_table("user_preferences", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=False), sa.Column("weight", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("feedback", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False), sa.Column("label", sa.Enum("INTERESTING", "NEUTRAL", "NOT_INTERESTING", name="feedbacktype"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("digests", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("digest_items", sa.Column("digest_id", sa.Integer(), sa.ForeignKey("digests.id"), primary_key=True), sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), primary_key=True), sa.Column("rank", sa.Integer(), nullable=False))


def downgrade() -> None:
    op.drop_table("digest_items")
    op.drop_table("digests")
    op.drop_table("feedback")
    op.drop_table("user_preferences")
    op.drop_table("article_topics")
    op.drop_table("articles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("topics")
    op.drop_table("article_sources")
    op.execute("DROP TYPE IF EXISTS feedbacktype")
