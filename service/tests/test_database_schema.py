from app.database import Base
from app.todos.model import Todo


def test_todo_model_describes_todos_table() -> None:
    table = Base.metadata.tables[Todo.__tablename__]

    assert table.name == "todos"
    assert {column.name for column in table.columns} == {
        "id",
        "title",
        "completed",
        "created_at",
    }
