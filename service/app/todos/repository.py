from app.database import get_connection


class TodoRepository:
    def list(self) -> list[dict]:
        with get_connection() as connection:
            return list(
                connection.execute(
                    "SELECT id, title, completed, created_at FROM todos ORDER BY id"
                ).fetchall()
            )

    def get(self, todo_id: int) -> dict | None:
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, title, completed, created_at FROM todos WHERE id = %s",
                (todo_id,),
            ).fetchone()

    def create(self, title: str) -> dict:
        with get_connection() as connection:
            return connection.execute(
                """
                INSERT INTO todos (title)
                VALUES (%s)
                RETURNING id, title, completed, created_at
                """,
                (title,),
            ).fetchone()

    def update(self, todo_id: int, values: dict) -> dict | None:
        if not values:
            return self.get(todo_id)

        assignments = []
        parameters = []
        for field in ("title", "completed"):
            if field in values:
                assignments.append(f"{field} = %s")
                parameters.append(values[field])

        parameters.append(todo_id)
        with get_connection() as connection:
            return connection.execute(
                f"""
                UPDATE todos
                SET {", ".join(assignments)}
                WHERE id = %s
                RETURNING id, title, completed, created_at
                """,
                parameters,
            ).fetchone()

    def delete(self, todo_id: int) -> bool:
        with get_connection() as connection:
            result = connection.execute(
                "DELETE FROM todos WHERE id = %s", (todo_id,)
            )
            return result.rowcount > 0


todo_repository = TodoRepository()
