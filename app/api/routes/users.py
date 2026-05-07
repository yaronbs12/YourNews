from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import UserCreate, UserPreferenceRead, UserRead
from app.models.topic import Topic
from app.models.user import User
from app.models.user_preference import UserPreference

router = APIRouter()


@router.post("/users", response_model=UserRead)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    """Create a user, returning the existing row when the email already exists."""

    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        return UserRead(id=existing_user.id, email=existing_user.email, created_at=existing_user.created_at)

    user = User(email=payload.email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserRead(id=user.id, email=user.email, created_at=user.created_at)


@router.get("/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    users = db.scalars(select(User).order_by(User.id.asc())).all()
    return [UserRead(id=user.id, email=user.email, created_at=user.created_at) for user in users]


@router.get("/users/{user_id}/preferences", response_model=list[UserPreferenceRead])
def list_user_preferences(user_id: int, db: Session = Depends(get_db)) -> list[UserPreferenceRead]:
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    rows = db.execute(
        select(Topic.name, func.sum(UserPreference.weight).label("weight"))
        .join(UserPreference, UserPreference.topic_id == Topic.id)
        .where(UserPreference.user_id == user_id)
        .group_by(Topic.name)
        .order_by(func.sum(UserPreference.weight).desc(), Topic.name.asc())
    ).all()
    return [UserPreferenceRead(topic=topic, weight=weight) for topic, weight in rows]
