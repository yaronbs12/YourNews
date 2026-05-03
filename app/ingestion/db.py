from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.schemas import NormalizedArticle
from app.models.article import Article
from app.models.article_source import ArticleSource


def get_or_create_article_source(session: Session, name: str, url: str) -> ArticleSource:
    source = session.scalar(select(ArticleSource).where(ArticleSource.url == url))
    if source is not None:
        return source

    source = session.scalar(select(ArticleSource).where(ArticleSource.name == name))
    if source is not None:
        return source

    source = ArticleSource(name=name, url=url, source_type="rss", enabled=True)
    session.add(source)
    session.flush()
    return source


def insert_new_articles(session: Session, articles: list[NormalizedArticle]) -> list[Article]:
    inserted: list[Article] = []
    seen_urls: set[str] = set()

    for article in articles:
        if article.url in seen_urls:
            continue

        seen_urls.add(article.url)
        existing = session.scalar(select(Article).where(Article.url == article.url))
        if existing is not None:
            continue

        source = get_or_create_article_source(
            session=session,
            name=article.source,
            url=article.source_url,
        )
        db_article = Article(
            source_id=source.id,
            title=article.title,
            url=article.url,
            content=article.content,
            published_at=article.published_at,
        )
        session.add(db_article)
        inserted.append(db_article)

    session.flush()
    return inserted
