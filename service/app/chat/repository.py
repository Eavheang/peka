from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from psycopg.types.json import Jsonb

from app.chat.schemas import ChatResponse
from app.database import get_connection


class ConversationNotFoundError(LookupError):
    pass


class ConversationChangedError(Exception):
    """A regenerate's pinned pair is no longer the last turn."""


class ChatRepository:
    def create_exchange(
        self,
        owner_id: UUID,
        title: str,
        query: str,
        response: ChatResponse,
        conversation_id: UUID | None = None,
        status: Literal["completed", "stopped"] = "completed",
        new_conversation_id: UUID | None = None,
        # Ids of the user+assistant pair a regenerate replaces. Pinned when the request
        # started, so a turn added meanwhile is never the one deleted.
        replace_ids: tuple[UUID, UUID] | None = None,
    ) -> dict[str, Any]:
        citations = [citation.model_dump(mode="json") for citation in response.citations]
        with get_connection() as connection:
            if conversation_id is None:
                conversation = connection.execute(
                    "INSERT INTO conversations (id, owner_id, title) "
                    "VALUES (COALESCE(%s, gen_random_uuid()), %s, %s) "
                    "RETURNING id, owner_id, title, created_at, updated_at",
                    (new_conversation_id, owner_id, title),
                ).fetchone()
            else:
                conversation = connection.execute(
                    "SELECT id, owner_id, title, created_at, updated_at FROM conversations "
                    "WHERE id = %s AND owner_id = %s FOR UPDATE",
                    (conversation_id, owner_id),
                ).fetchone()
                if conversation is None:
                    raise ConversationNotFoundError

                conversation = connection.execute(
                    "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = %s RETURNING id, owner_id, title, created_at, updated_at",
                    (conversation_id,),
                ).fetchone()

            if conversation is None:
                raise RuntimeError("Unable to create conversation")

            if replace_ids is not None:
                removed = connection.execute(
                    "DELETE FROM messages WHERE id IN ("
                    "SELECT id FROM messages WHERE conversation_id = %s ORDER BY sequence DESC LIMIT 2"
                    ") RETURNING id",
                    (conversation["id"],),
                ).fetchall()
                # The pair is gone or no longer last (another tab or a new message); roll back.
                if {row["id"] for row in removed} != set(replace_ids):
                    raise ConversationChangedError

            next_sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), -1) + 1 AS next_sequence "
                "FROM messages WHERE conversation_id = %s",
                (conversation["id"],),
            ).fetchone()["next_sequence"]
            user_message = connection.execute(
                "INSERT INTO messages "
                "(conversation_id, sequence, role, content, refused, citations, status) "
                "VALUES (%s, %s, 'user', %s, false, %s, 'completed') "
                "RETURNING id, role, content, refused, citations, status, created_at",
                (conversation["id"], next_sequence, query, Jsonb([])),
            ).fetchone()
            assistant_message = connection.execute(
                "INSERT INTO messages "
                "(conversation_id, sequence, role, content, refused, citations, status) "
                "VALUES (%s, %s, 'assistant', %s, %s, %s, %s) "
                "RETURNING id, role, content, refused, citations, status, created_at",
                (
                    conversation["id"], next_sequence + 1, response.answer, response.refused,
                    Jsonb(citations), status,
                ),
            ).fetchone()
            if user_message is None or assistant_message is None:
                raise RuntimeError("Unable to persist chat messages")

            return {
                "conversation": cast(dict[str, Any], conversation),
                "messages": [cast(dict[str, Any], user_message), cast(dict[str, Any], assistant_message)],
            }

    def list_owned(
        self,
        owner_id: UUID,
        limit: int,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> list[dict[str, Any]]:
        with get_connection() as connection:
            query = (
                "SELECT id, owner_id, title, created_at, updated_at FROM conversations "
                "WHERE owner_id = %s"
            )
            params: list[Any] = [owner_id]
            if cursor is not None:
                query += " AND (updated_at, id) < (%s, %s)"
                params.extend(cursor)
            query += " ORDER BY updated_at DESC, id DESC LIMIT %s"
            params.append(limit)
            rows = connection.execute(
                query,
                tuple(params),
            ).fetchall()
            return cast(list[dict[str, Any]], rows)

    def get_owned(self, conversation_id: UUID, owner_id: UUID) -> dict[str, Any] | None:
        with get_connection() as connection:
            conversation = connection.execute(
                "SELECT id, owner_id, title, created_at, updated_at FROM conversations "
                "WHERE id = %s AND owner_id = %s",
                (conversation_id, owner_id),
            ).fetchone()
            if conversation is None:
                return None
            messages = connection.execute(
                "SELECT id, role, content, refused, citations, status, created_at FROM messages "
                "WHERE conversation_id = %s ORDER BY sequence",
                (conversation_id,),
            ).fetchall()
            result = cast(dict[str, Any], conversation)
            result["messages"] = cast(list[dict[str, Any]], messages)
            return result

    def delete_owned(self, conversation_id: UUID, owner_id: UUID) -> bool:
        with get_connection() as connection:
            result = connection.execute(
                "DELETE FROM conversations WHERE id = %s AND owner_id = %s",
                (conversation_id, owner_id),
            )
            return result.rowcount > 0


chat_repository = ChatRepository()
