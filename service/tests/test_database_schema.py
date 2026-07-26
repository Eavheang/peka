from app.database import Base
from app.auth.model import User


def test_user_model_describes_users_table() -> None:
    table = Base.metadata.tables[User.__tablename__]

    assert table.name == "users"
    assert {column.name for column in table.columns} == {
        "id",
        "email",
        "password_hash",
        "role",
        "token_version",
        "created_at",
        "updated_at",
    }
