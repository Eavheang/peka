from app.database import Base
from app.auth.model import User
from app.files.model import StoredFile


def test_user_model_describes_users_table() -> None:
    table = Base.metadata.tables[User.__tablename__]

    assert table.name == "users"
    assert {column.name for column in table.columns} == {
        "id",
        "email",
        "password_hash",
        "role",
        "token_version",
        "is_active",
        "created_at",
        "updated_at",
    }


def test_file_model_keeps_minimal_metadata() -> None:
    table = Base.metadata.tables[StoredFile.__tablename__]

    assert {column.name for column in table.columns} == {
        "id",
        "path",
        "content_type",
        "author_id",
        "created_at",
    }
