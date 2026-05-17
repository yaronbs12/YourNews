from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.models import *  # noqa: F403,F401
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference


def _setup_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def test_post_users_creates_user() -> None:
    client, _ = _setup_client()

    response = client.post("/users", json={"email": "reader@example.com"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["email"] == "reader@example.com"
    assert "created_at" in data


def test_post_users_duplicate_email_returns_existing_user() -> None:
    client, SessionLocal = _setup_client()

    first_response = client.post("/users", json={"email": "duplicate@example.com"})
    second_response = client.post("/users", json={"email": "duplicate@example.com"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    with SessionLocal() as session:
        assert session.query(User).filter_by(email="duplicate@example.com").count() == 1


def test_get_users_returns_users_ordered_by_id() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        session.add_all([User(email="first@example.com"), User(email="second@example.com")])
        session.commit()

    response = client.get("/users")

    assert response.status_code == 200
    data = response.json()
    assert [item["email"] for item in data] == ["first@example.com", "second@example.com"]
    assert [item["id"] for item in data] == [1, 2]


def test_get_user_preferences_returns_topic_weights_ordered_by_weight_then_topic() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        user = User(email="prefs@example.com")
        ai = Topic(name="ai")
        business = Topic(name="business")
        cybersecurity = Topic(name="cybersecurity")
        session.add_all([user, ai, business, cybersecurity])
        session.flush()
        session.add_all(
            [
                UserPreference(user_id=user.id, topic_id=cybersecurity.id, weight=-2),
                UserPreference(user_id=user.id, topic_id=business.id, weight=4),
                UserPreference(user_id=user.id, topic_id=ai.id, weight=4),
            ]
        )
        user_id = user.id
        session.commit()

    response = client.get(f"/users/{user_id}/preferences")

    assert response.status_code == 200
    assert response.json() == [
        {"topic": "ai", "weight": 4},
        {"topic": "business", "weight": 4},
        {"topic": "cybersecurity", "weight": -2},
    ]


def test_get_user_preferences_unknown_user_id_returns_404() -> None:
    client, _ = _setup_client()

    response = client.get("/users/999/preferences")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_get_user_preferences_without_preferences_returns_empty_list() -> None:
    client, SessionLocal = _setup_client()
    with SessionLocal() as session:
        user = User(email="empty-prefs@example.com")
        session.add(user)
        session.flush()
        user_id = user.id
        session.commit()

    response = client.get(f"/users/{user_id}/preferences")

    assert response.status_code == 200
    assert response.json() == []
