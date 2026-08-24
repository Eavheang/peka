
from app.chat.schemas import ChatResponse, Citation
from app.engine.llm_client import chat_completion
from app.engine.search.service import search_knowledge

REFUSAL_MESSAGE = "I cannot answer this question from the knowledge base."

EVIDENCE_FLOOR = 1  # at least one retrieved chunk above the similarity floor required

_SYSTEM_PROMPT = (
    "You answer questions strictly from the provided knowledge-base excerpts. "
    "Cite every claim with the excerpt number in square brackets, e.g. [1]. "
    "If the excerpts do not contain the answer, reply exactly that you cannot "
    "answer from the knowledge base. Never use outside knowledge."
)


def _citations(results: list[dict]) -> list[Citation]:
    citations = []
    for result in results:
        pages = [
            loc.get("page")
            for loc in result["source_locations"]
            if isinstance(loc, dict) and loc.get("page") is not None
        ]
        citations.append(
            Citation(
                title=result["title"],
                heading=result["heading"],
                page=min(pages) if pages else None,
                source_locations=result["source_locations"],
            )
        )
    return citations


def _build_user_prompt(query: str, results: list[dict]) -> str:
    excerpts = "\n\n".join(
        f"[{index}] {result['title']} — {result['heading']}\n{result['snippet']}"
        for index, result in enumerate(results, start=1)
    )
    return f"Question: {query}\n\nKnowledge-base excerpts:\n{excerpts}"


def answer_from_knowledge(query: str, user_role: str) -> ChatResponse:
    results = search_knowledge(query, user_role)
    if len(results) < EVIDENCE_FLOOR:
        return ChatResponse(answer=REFUSAL_MESSAGE, refused=True, citations=[])
    content = chat_completion(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(query, results)},
        ]
    )
    return ChatResponse(answer=content, refused=False, citations=_citations(results))
