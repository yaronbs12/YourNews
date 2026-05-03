from datetime import datetime

from pydantic import BaseModel

__all__ = [
    "ArticleRead",
    "SourceRead",
    "DigestPreviewItem",
    "DigestPreview",
]


class ArticleRead(BaseModel):
    id: int
    title: str
    url: str
    content: str | None
    published_at: datetime | None
    created_at: datetime
    source_name: str


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


class DigestPreview(BaseModel):
    """Read-only digest preview payload."""

    items: list[DigestPreviewItem]
