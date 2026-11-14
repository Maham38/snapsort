from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import firebase_admin
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth, credentials
from firebase_admin import _auth_utils, exceptions
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Role, User


@lru_cache
def firebase_app() -> firebase_admin.App:
    settings = get_settings()
    if settings.firebase_credentials_file:
        path = Path(settings.firebase_credentials_file)
        if not path.is_file():
            raise RuntimeError(f"Firebase credentials file does not exist: {path}")
        return firebase_admin.initialize_app(
            credentials.Certificate(str(path)),
            {"projectId": settings.firebase_project_id}
            if settings.firebase_project_id
            else None,
        )
    if settings.firebase_project_id:
        return firebase_admin.initialize_app(
            options={"projectId": settings.firebase_project_id}
        )
    raise RuntimeError(
        "Firebase is not configured. Set FIREBASE_CREDENTIALS_FILE or "
        "FIREBASE_PROJECT_ID."
    )


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        decoded = auth.verify_id_token(authorization[7:], app=firebase_app())
    except (
        ValueError,
        _auth_utils.InvalidIdTokenError,
        exceptions.FirebaseError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase ID token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    user_id = decoded["uid"]
    user = db.get(User, user_id)
    if user is None:
        user = User(
            id=user_id,
            email=decoded.get("email", ""),
            display_name=decoded.get("name"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def require_roles(*roles: Role) -> Callable:
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This role is not allowed to perform this action",
            )
        return user

    return dependency
