from app.database import Base
from app.audit.model import AuditEventRecord
from app.auth.model import Invitation, User
from app.files.model import StoredFile
from app.engine.indexing.job_model import IndexJob
from app.engine.chunks.chunk_model import KnowledgeChunk
from app.engine.chunks.chunk_set_model import ChunkSet

def test_user_model_describes_users_table() -> None:
    table = Base.metadata.tables[User.__tablename__]

    assert table.name == "users"
    assert {column.name for column in table.columns} == {
        "id",
        "email",
        "display_name",
        "password_hash",
        "role",
        "token_version",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert str(next(constraint for constraint in table.constraints
                    if constraint.name == "users_role_check").sqltext) == (
        "role IN ('admin', 'senior', 'staff')"
    )


def test_audit_event_model_describes_audit_events_table() -> None:
    table = Base.metadata.tables[AuditEventRecord.__tablename__]

    assert {column.name for column in table.columns} == {
        "id",
        "type",
        "actor_id",
        "summary",
        "metadata",
        "created_at",
    }
    assert table.c.actor_id.nullable
    assert str(next(constraint for constraint in table.constraints
                    if constraint.name == "audit_events_type_check").sqltext) == (
        "type IN ('sync', 'query', 'system')"
    )
    assert {index.name for index in table.indexes} == {
        "audit_events_type_created_at_idx",
        "audit_events_created_at_idx",
    }


def test_invitation_model_stores_a_token_hash_not_the_token() -> None:
    table = Base.metadata.tables[Invitation.__tablename__]

    assert {column.name for column in table.columns} == {
        "id",
        "email",
        "role",
        "token_hash",
        "invited_by",
        "expires_at",
        "accepted_at",
        "created_at",
    }


def test_file_model_keeps_minimal_metadata() -> None:
    table = Base.metadata.tables[StoredFile.__tablename__]

    assert {column.name for column in table.columns} == {
        "id",
        "path",
        "content_type",
        "sha256",
        "author_id",
        "access_level",
        "created_at",
    }
    assert str(next(constraint for constraint in table.constraints
                    if constraint.name == "files_access_level_check").sqltext) == (
        "access_level IN ('general', 'confidential')"
    )


def test_index_job_model_keeps_minimal_queue_state() -> None:
    table = Base.metadata.tables[IndexJob.__tablename__]

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
        "chunk_set_id",
        "heading",
        "content",
        "source_locations",
        "embedding",
    }


def test_chunk_set_model_describes_versioned_sets() -> None:
    table = Base.metadata.tables[ChunkSet.__tablename__]

    assert table.name == "chunk_sets"
    assert {column.name for column in table.columns} == {
        "id",
        "file_id",
        "status",
        "chunker_version",
        "created_at",
    }
    assert str(next(constraint for constraint in table.constraints
                    if constraint.name == "chunk_sets_status_check").sqltext) == (
        "status IN ('building', 'active', 'superseded')"
    )
