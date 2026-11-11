"""
SQLAlchemy 数据库连接与会话管理引擎 (SQLAlchemy Database Engine)
支持 PostgreSQL (驱动 psycopg2 / asyncpg)，并具备高可用本地回退机制。
管理数据库连接池 (Connection Pool)、Session 会话生命周期与元数据建表。
"""

import os
from contextlib import contextmanager
from typing import Generator
from core.logger import log, cprint, LogColor
from config import settings

# 导入 SQLAlchemy 核心组件
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker, declarative_base, Session
    from sqlalchemy.pool import QueuePool
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    log.warning("SQLAlchemy 未安装，将使用兼容模式")

Base = declarative_base() if SQLALCHEMY_AVAILABLE else object

# 默认 PostgreSQL 连接串与备用本地数据库
POSTGRES_URL = getattr(settings, "DATABASE_URL", os.getenv(
    "DATABASE_URL", 
    os.getenv("POSTGRES_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/intelliserve")
))

SQLITE_FALLBACK_URL = "sqlite:///./data/intelliserve.db"

_engine = None
_SessionLocal = None
_active_dialect = "postgresql"


def get_engine():
    """获取或初始化 SQLAlchemy 引擎"""
    global _engine, _SessionLocal, _active_dialect

    if _engine is not None:
        return _engine

    if not SQLALCHEMY_AVAILABLE:
        return None

    # 优先尝试连接目标 PostgreSQL 数据库
    target_url = POSTGRES_URL
    is_sqlite = target_url.startswith("sqlite")

    try:
        if is_sqlite:
            # 本地 SQLite
            _engine = create_engine(
                target_url,
                connect_args={"check_same_thread": False},
                echo=getattr(settings, "DB_ECHO", False)
            )
            _active_dialect = "sqlite"
            cprint(f"[SQLAlchemy] 已连接本地嵌入式数据库: {target_url}", LogColor.GREEN)
        else:
            # PostgreSQL 生产/开发连接池
            pool_size = getattr(settings, "DB_POOL_SIZE", 10)
            max_overflow = getattr(settings, "DB_MAX_OVERFLOW", 20)

            _engine = create_engine(
                target_url,
                poolclass=QueuePool,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_pre_ping=True,  # 探活防断连
                pool_recycle=3600,   # 定期回收连接
                echo=getattr(settings, "DB_ECHO", False)
            )
            # 快速轻量探活测试
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
            _active_dialect = "postgresql"
            cprint(f"[SQLAlchemy] 成功连接 PostgreSQL 数据库 ({target_url.split('@')[-1] if '@' in target_url else target_url})", LogColor.GREEN)

    except Exception as e:
        log.warning(f"[SQLAlchemy] 目标 PostgreSQL 连接不可用 ({e})，自动切换至 SQLite 本地高可用热备数据库")
        # 优雅平滑回退至 SQLite 引擎，确保服务不中断
        os.makedirs("./data", exist_ok=True)
        _engine = create_engine(
            SQLITE_FALLBACK_URL,
            connect_args={"check_same_thread": False},
            echo=getattr(settings, "DB_ECHO", False)
        )
        _active_dialect = "sqlite"
        cprint(f"[SQLAlchemy] 已启动 SQLite 本地高可用存储引擎: {SQLITE_FALLBACK_URL}", LogColor.CYAN)

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory():
    """获取 SessionLocal 会话工厂"""
    global _SessionLocal
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal


def get_active_dialect() -> str:
    """返回当前处于激活状态的数据库方言 (postgresql 或 sqlite)"""
    return _active_dialect


@contextmanager
def db_session_scope() -> Generator:
    """提供线程安全的事务性会话上下文管理器"""
    SessionLocal = get_session_factory()
    if SessionLocal is None:
        yield None
        return

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """FastAPI 依赖注入 (Depends) 会话生成器"""
    SessionLocal = get_session_factory()
    if SessionLocal is None:
        yield None
        return

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
