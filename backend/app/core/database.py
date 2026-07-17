from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def normalize_database_url(url: str) -> str:
    """统一成 SQLAlchemy 可用的驱动 URL。"""
    value = (url or "").strip()
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://") :]
    if value.startswith("postgresql://") and "+psycopg" not in value:
        return "postgresql+psycopg://" + value[len("postgresql://") :]
    return value


DATABASE_URL = normalize_database_url(settings.database_url)

# SQLite 需要这个参数，否则多线程下容易报错
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有数据表模型的基类。"""


def get_db() -> Generator[Session, None, None]:
    """每个请求拿一个数据库会话，用完自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
