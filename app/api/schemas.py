from datetime import datetime

from pydantic import BaseModel

__all__ = [
    "ArticleRead",
    "SourceRead",
    "DigestPreviewItem",
    "DigestPreview",
    "FeedbackCreate",
    "FeedbackRead",
]


class ArticleRead(BaseModel):
    id: int
    title: str
    url: str
    content: str | None
    published_at: datetime | None
    created_at: datetime
    source_name: str
    topics: list[str]


class SourceRead(BaseModel):
    id: int
    name: str
    url: str
    source_type: str
    enabled: bool
    last_fetched_at: datetime | None


class DigestPreviewItem(BaseModel):
    """Single preview row for digest candidates."""

    rank: int
    article_id: int
    title: str
    url: str
    source_name: str
    published_at: datetime | None
    created_at: datetime
    topics: list[str]


class DigestPreview(BaseModel):
    """Read-only digest preview payload."""

    items: list[DigestPreviewItem]


class FeedbackCreate(BaseModel):
    user_id: int
    article_id: int
    label: str


class FeedbackRead(BaseModel):
    id: int
    user_id: int
    article_id: int
    label: str
    created_at: datetime
