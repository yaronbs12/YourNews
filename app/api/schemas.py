from datetime import datetime

from pydantic import BaseModel

__all__ = [
    "ArticleRead",
    "SourceRead",
    "DigestPreviewItem",
    "DigestPreview",
    "DigestScoreBreakdown",
    "DigestItemRead",
    "DigestRead",
    "DigestSummaryRead",
    "FeedbackCreate",
    "FeedbackRead",
    "UserCreate",
    "UserRead",
    "UserPreferenceRead",
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


class DigestScoreBreakdown(BaseModel):
    """Explainable score components for a digest candidate."""

    total_score: int
    topic_score: int
    preference_score: int
    freshness_score: int
    source_penalty: int


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
    score: int
    score_breakdown: DigestScoreBreakdown


class DigestPreview(BaseModel):
    """Read-only digest preview payload."""

    items: list[DigestPreviewItem]


class DigestItemRead(BaseModel):
    rank: int
    article_id: int
    title: str
    url: str
    source_name: str
    topics: list[str]


class DigestRead(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    items: list[DigestItemRead]


class DigestSummaryRead(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    item_count: int


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


class UserCreate(BaseModel):
    email: str


class UserRead(BaseModel):
    id: int
    email: str
    created_at: datetime


class UserPreferenceRead(BaseModel):
    topic: str
    weight: int
