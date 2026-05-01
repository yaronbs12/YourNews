from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NormalizedArticle:
    title: str
    url: str
    content: str | None
    published_at: datetime | None
    source: str
    source_url: str
