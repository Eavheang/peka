from datetime import UTC, datetime


class TodoRepository:
    def __init__(self) -> None:
        self._todos: dict[int, dict] = {}
        self._next_id = 1

    def list(self) -> list[dict]:
        return list(self._todos.values())

    def get(self, todo_id: int) -> dict | None:
        return self._todos.get(todo_id)

    def create(self, title: str) -> dict:
        todo = {
            "id": self._next_id,
            "title": title,
            "completed": False,
            "created_at": datetime.now(UTC),
        }
        self._todos[self._next_id] = todo
        self._next_id += 1
        return todo

    def update(self, todo_id: int, values: dict) -> dict | None:
        todo = self.get(todo_id)
        if todo is None:
            return None
        todo.update(values)
        return todo

    def delete(self, todo_id: int) -> bool:
        return self._todos.pop(todo_id, None) is not None


todo_repository = TodoRepository()
