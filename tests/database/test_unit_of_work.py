from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import ProgrammingError

from kart.app.database import create_database_engine, unit_of_work
from kart.app.migrate import migrate

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def engine(empty_database_url: str) -> Iterator[Engine]:
    migrate(empty_database_url)
    engine = create_database_engine(empty_database_url)
    with unit_of_work(engine, "ordering") as session:
        session.execute(text("CREATE TABLE carts (id integer)"))
    yield engine
    engine.dispose()


def test_a_context_commits_to_its_own_schema(engine: Engine) -> None:
    with unit_of_work(engine, "ordering") as session:
        session.execute(text("INSERT INTO carts VALUES (1)"))

    with unit_of_work(engine, "ordering") as session:
        assert session.scalars(text("SELECT id FROM ordering.carts")).all() == [1]


def _insert_then_fail(engine: Engine) -> None:
    with unit_of_work(engine, "ordering") as session:
        session.execute(text("INSERT INTO carts VALUES (1)"))
        raise RuntimeError


def test_a_failed_unit_of_work_leaves_nothing_behind(engine: Engine) -> None:
    with pytest.raises(RuntimeError):
        _insert_then_fail(engine)

    with unit_of_work(engine, "ordering") as session:
        assert session.scalars(text("SELECT id FROM carts")).all() == []


def test_a_context_cannot_read_another_contexts_schema(engine: Engine) -> None:
    with (
        pytest.raises(ProgrammingError, match="permission denied for schema ordering"),
        unit_of_work(engine, "catalog") as session,
    ):
        session.execute(text("SELECT id FROM ordering.carts"))
