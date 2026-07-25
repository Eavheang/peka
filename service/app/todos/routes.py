from fastapi import APIRouter, status

from app.todos.schemas import TodoCreate, TodoResponse, TodoUpdate
from app.todos.service import create_todo, delete_todo, list_todos, update_todo


router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("", response_model=list[TodoResponse])
async def get_todos() -> list[dict]:
    return list_todos()


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def add_todo(data: TodoCreate) -> dict:
    return create_todo(data)


@router.patch("/{todo_id}", response_model=TodoResponse)
async def edit_todo(todo_id: int, data: TodoUpdate) -> dict:
    return update_todo(todo_id, data)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_todo(todo_id: int) -> None:
    delete_todo(todo_id)
