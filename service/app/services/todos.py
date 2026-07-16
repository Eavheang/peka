from fastapi import HTTPException, status

from app.repositories.todos import todo_repository
from app.schemas.todos import TodoCreate, TodoUpdate


def list_todos() -> list[dict]:
    return todo_repository.list()


def create_todo(data: TodoCreate) -> dict:
    return todo_repository.create(data.title)


def update_todo(todo_id: int, data: TodoUpdate) -> dict:
    todo = todo_repository.update(todo_id, data.model_dump(exclude_unset=True))
    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    return todo


def delete_todo(todo_id: int) -> None:
    if not todo_repository.delete(todo_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
