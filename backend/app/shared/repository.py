"""Base generic repository class encapsulating common SQLAlchemy 2.0 data-access patterns."""

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """Abstract base repository for domain data-access layers."""

    def __init__(self, db: Session) -> None:
        self.db = db

