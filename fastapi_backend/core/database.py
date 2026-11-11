"""
SQLAlchemy 数据库连接与会话管理引擎 (SQLAlchemy Database Engine)
专门面向 PostgreSQL 关系型数据库 (驱动 psycopg2 / asyncpg)。
管理数据库连接池 (Connection Pool)、Session 会话生命周期与元数据建表。
"""

import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
from core.logger import log, cprint, LogColor
from config import settings

# 声明式 ORM 基类
Base = declarative_base()

# PostgreSQL 目标数据库连接串
POSTGRES_URL = getattr(settings, "DATABASE_URL", os.getenv(
    "DATABASE_URL", 
    os.getenv("POSTGRES_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/intelliserve")
))

_engine = None
_SessionLocal = None


def get_engine():
    """初始化并获取 PostgreSQL SQLAlchemy 数据库引擎"""
    global _engine, _SessionLocal

    if _engine is not None:
        return _engine

    target_url = POSTGRES_URL
    pool_size = getattr(settings, "DB_POOL_SIZE", 10)
    max_overflow = getattr(settings, "DB_MAX_OVERFLOW", 20)

    # 创建 PostgreSQL 专属连接池引擎
    _engine = create_engine(
        target_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,  # 自动探活防断连
        pool_recycle=3600,   # 定期回收连接
        echo=getattr(settings, "DB_ECHO", False)
    )

    cprint(f"[SQLAlchemy] 数据库引擎初始化成功，已连接 PostgreSQL ({target_url.split('@')[-1] if '@' in target_url else target_url})", LogColor.GREEN)

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory():
    """获取 SessionLocal 会话工厂"""
    global _SessionLocal
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal


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
    finally:
        db.close()
