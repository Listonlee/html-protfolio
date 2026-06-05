"""SQLAlchemy 引擎 + session。

本機 SQLite、上雲 Postgres,同一份 code,靠 DATABASE_URL 切換。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import config

connect_args = {}
if config.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    config.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Postgres 連線斷咗自動重連
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency:每個 request 一個 session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401  確保 model 已 import 先建表
    Base.metadata.create_all(bind=engine)
