from pathlib import Path

from src.vector.indexers.doc_indexer import DocVectorIndexer
from src.vector.local_vector_store import LocalVectorStore


class FakeEmbeddingProvider:
    def embed_batch(self, texts, batch_size=16):
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_doc_indexer_builds_embeddings(tmp_path, monkeypatch):
    config = {"openai": {"embedding_model": "text-embedding-3-small"}}
    store_path = tmp_path / "doc_index.json"
    indexer = DocVectorIndexer(
        config,
        docs_root=Path("data/synthetic_git"),
        output_path=store_path,
        vector_store=LocalVectorStore(store_path),
        embedding_provider=FakeEmbeddingProvider(),
    )
    result = indexer.build()
    assert result["indexed"] >= 1

    records = store_path.read_text()
    assert "doc:docs/payments_api.md" in records

