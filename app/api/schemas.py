from datetime import datetime

from pydantic import BaseModel


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
    rank: int
    article_id: int
    title: str
    url: str
    source_name: str
    published_at: datetime | None
    created_at: datetime


class DigestPreview(BaseModel):
    items: list[DigestPreviewItem]
