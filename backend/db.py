"""SQLAlchemy engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_engine = None
_Session = None


def init(database_url: str) -> None:
    global _engine, _Session
    _engine = create_engine(database_url)
    _Session = sessionmaker(bind=_engine)


def get_session():
    if _Session is None:
        raise RuntimeError("db.init() not called")
    return _Session()


class Base(DeclarativeBase):
    pass
