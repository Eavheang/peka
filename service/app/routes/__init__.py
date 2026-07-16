from fastapi import APIRouter

from app.routes.todos import router as todos_router

routers: list[APIRouter] = [todos_router]
