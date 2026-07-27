from psycopg.rows import dict_row

from app import database


class FakePool:
    def __init__(self, conninfo, kwargs=None, open=False):
        self.conninfo = conninfo
        self.kwargs = kwargs
        self.open = open
        self.closed = False

    def connection(self):
        return "connection-context"

    def close(self):
        self.closed = True


def test_get_connection_reuses_one_pool_with_dict_rows(monkeypatch):
    created = []
    monkeypatch.setattr(database, "_pool", None, raising=False)
    monkeypatch.setattr(
        database, "ConnectionPool",
        lambda conninfo, kwargs=None, open=False: created.append(FakePool(conninfo, kwargs, open)) or created[-1],
        raising=False,
    )

    first = database.get_connection()
    second = database.get_connection()

    assert first == "connection-context" and second == "connection-context"
    assert len(created) == 1
    assert created[0].kwargs == {"row_factory": dict_row}
    assert created[0].open is True


def test_lifespan_closes_pool_on_shutdown(monkeypatch):
    import asyncio

    from app import main

    pool = FakePool("conninfo")
    monkeypatch.setattr(database, "_pool", pool, raising=False)

    async def run_lifespan():
        async with main.lifespan(main.app):
            pass

    asyncio.run(run_lifespan())

    assert pool.closed is True


def test_close_pool_closes_and_resets(monkeypatch):
    pool = FakePool("conninfo")
    monkeypatch.setattr(database, "_pool", pool, raising=False)

    database.close_pool()

    assert pool.closed is True
    assert database._pool is None
