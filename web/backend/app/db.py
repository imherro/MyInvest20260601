from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DB_PATH


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    return f"sqlite:///{DB_PATH.as_posix()}"


engine = create_engine(database_url(), connect_args={"check_same_thread": False}, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def reset_database() -> None:
    from .models.current_state import Base as ModelsBase

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ModelsBase.metadata.drop_all(bind=engine)
    ModelsBase.metadata.create_all(bind=engine)
