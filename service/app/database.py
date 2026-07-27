import threading
from contextlib import AbstractContextManager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool(settings.database_url, kwargs={"row_factory": dict_row}, open=True)
    return _pool


def get_connection() -> AbstractContextManager[psycopg.Connection]:
    return _get_pool().connection()


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None
