from app.engine.chunks import embeddings
from app.engine.chunks.chunker import OKFChunk


def test_embed_chunks_batches_and_preserves_response_order(monkeypatch):
    chunks = [
        OKFChunk("A", "One", text, ())
        for text in ("first", "second", "third")
    ]
    requests = []

    class Response:
        def __init__(self, count):
            self.count = count

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "data": [
                    {"index": index, "embedding": [float(index)] * 3}
                    for index in reversed(range(self.count))
                ]
            }

    def post(url, **kwargs):
        requests.append(kwargs["json"]["input"])
        return Response(len(kwargs["json"]["input"]))

    monkeypatch.setattr(embeddings.httpx, "post", post)
    monkeypatch.setattr(embeddings.settings, "embedding_base_url", "http://embeddings:80/v1")
    monkeypatch.setattr(embeddings.settings, "embedding_model", "BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(embeddings.settings, "embedding_dimensions", 3)
    monkeypatch.setattr(embeddings.settings, "embedding_batch_size", 2)

    vectors = embeddings.embed_chunks(chunks)

    assert [len(batch) for batch in requests] == [2, 1]
    assert vectors == [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0]]
