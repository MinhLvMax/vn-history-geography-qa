"""Khởi tạo engine, tạo bảng và quản lý phiên làm việc SQLAlchemy."""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.infrastructure.persistence.sqlalchemy.orm_models import Base


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite mặc định tắt khóa ngoại, cần bật để ON DELETE CASCADE hoạt động."""

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_database(url: str, echo: bool = False) -> sessionmaker[Session]:
    """Tạo engine từ URL kết nối, đảm bảo các bảng đã tồn tại và trả về session factory.

    Ví dụ URL: 'sqlite:///path/to/db.sqlite3', 'postgresql+psycopg://user:pass@host/db'.
    """
    engine = create_engine(url, echo=echo)
    if engine.dialect.name == "sqlite":
        _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
