"""
SQLAlchemy 数据库连接与会话管理引擎 (SQLAlchemy Database Engine)
统一基于 PostgreSQL + Psycopg 3 (postgresql+psycopg://) 驱动，与 LangGraph Checkpointer 共用一套底层驱动。
管理数据库连接池 (Connection Pool)、Session 会话生命周期与元数据建表。
"""

import threading
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
from core.logger import cprint, LogColor
from config import settings

# 声明式 ORM 基类
Base = declarative_base()


def _normalize_sqlalchemy_pg_url(url: str) -> str:
    """统一将 postgresql+psycopg2://、postgres://、postgresql:// 等连接串规范化为 postgresql+psycopg://"""
    cleaned = url.strip()
    if cleaned.startswith("postgresql+psycopg://"):
        return cleaned
    if cleaned.startswith("postgresql+") or cleaned.startswith("postgresql://") or cleaned.startswith("postgres://"):
        return "postgresql+psycopg://" + cleaned.split("://", 1)[1]
    return cleaned


def _mask_db_url(url: str) -> str:
    """使用 SQLAlchemy make_url 安全隐藏数据库密码（兼容密码含 @ 字符场景）"""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return url.split("@")[-1] if "@" in url else url


# PostgreSQL 目标数据库连接串（自动兼容旧 .env 中的 psycopg2 前缀，统一走 Psycopg 3）
POSTGRES_URL = _normalize_sqlalchemy_pg_url(settings.DATABASE_URL)

_engine_lock = threading.RLock()
_engine = None
_SessionLocal = None


def get_engine():
    """线程安全地初始化并获取 PostgreSQL SQLAlchemy 数据库引擎"""
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine

    with _engine_lock:
        if _engine is not None:
            return _engine

        target_url = POSTGRES_URL
        pool_size = getattr(settings, "DB_POOL_SIZE", 10)
        max_overflow = getattr(settings, "DB_MAX_OVERFLOW", 20)

        _engine = create_engine(
            target_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=getattr(settings, "DB_ECHO", False),
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

        cprint(f"[SQLAlchemy] 数据库引擎初始化成功，已连接 PostgreSQL ({_mask_db_url(target_url)})", LogColor.GREEN)
        return _engine


def get_session_factory():
    """获取 SessionLocal 会话工厂"""
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal


def dispose_engine() -> None:
    """释放 SQLAlchemy 连接池（应用关闭时调用）"""
    global _engine, _SessionLocal
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
            _engine = None
            _SessionLocal = None


def get_active_dialect() -> str:
    """返回当前数据库方言"""
    return "postgresql"


@contextmanager
def db_session_scope() -> Generator[Session, None, None]:
    """提供线程安全的事务性会话上下文管理器"""
    SessionLocal = get_session_factory()
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入 (Depends) 会话生成器"""
    SessionLocal = get_session_factory()
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
