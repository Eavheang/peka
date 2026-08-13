from app.database import Base
from app.auth.model import User
from app.files.model import StoredFile
from app.engine.OKFExtractor.model import OKFJob
from app.engine.chunked.model import KnowledgeChunk


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
        "sha256",
        "author_id",
        "created_at",
    }


def test_okf_job_model_keeps_minimal_queue_state() -> None:
    table = Base.metadata.tables[OKFJob.__tablename__]

    assert {column.name for column in table.columns} == {
        "file_id",
        "status",
        "attempts",
        "last_error",
        "updated_at",
    }


def test_knowledge_chunk_model_describes_pgvector_storage() -> None:
    table = Base.metadata.tables[KnowledgeChunk.__tablename__]

    assert {column.name for column in table.columns} == {
        "id",
        "file_id",
        "heading",
        "content",
        "source_locations",
        "embedding",
    }
