from pathlib import Path

from src.demo.scenario_classifier import PAYMENTS_SCENARIO
from src.demo.vector_retriever import VectorRetriever
from src.vector.indexers.slack_indexer import SlackVectorIndexer
from src.vector.indexers.git_indexer import GitVectorIndexer
from src.vector.indexers.doc_indexer import DocVectorIndexer
from src.vector.local_vector_store import LocalVectorStore


class FakeEmbeddingProvider:
    def embed_batch(self, texts, batch_size=32):
        return [[1.0 + idx * 0.1, 0.0, 0.0] for idx, _ in enumerate(texts)]

    def embed(self, text):
        return [1.0, 0.0, 0.0]


def _build_indexes(tmp_path, provider):
    config = {"openai": {"embedding_model": "text-embedding-3-small"}}

    slack_path = tmp_path / "slack.json"
    slack_indexer = SlackVectorIndexer(
        config,
        output_path=slack_path,
        embedding_provider=provider,
        vector_store=LocalVectorStore(slack_path),
    )
    slack_indexer.build()

    git_path = tmp_path / "git.json"
    git_indexer = GitVectorIndexer(
        config,
        output_path=git_path,
        embedding_provider=provider,
        vector_store=LocalVectorStore(git_path),
    )
    git_indexer.build()

    doc_path = tmp_path / "docs.json"
    doc_indexer = DocVectorIndexer(
        config,
        docs_root=Path("data/synthetic_git"),
        output_path=doc_path,
        embedding_provider=provider,
        vector_store=LocalVectorStore(doc_path),
    )
    doc_indexer.build()
    return config, {"slack": slack_path, "git": git_path, "docs": doc_path}


def test_vector_retriever_returns_snippets(tmp_path):
    provider = FakeEmbeddingProvider()
    config, store_paths = _build_indexes(tmp_path, provider)
    retriever = VectorRetriever(config, store_paths=store_paths, embedding_provider=provider)

    bundle = retriever.fetch_context(
        PAYMENTS_SCENARIO,
        question="Why is the payments API breaking?",
        top_k_slack=2,
        top_k_git=2,
        top_k_docs=2,
    )

    assert bundle.slack
    assert bundle.git
    assert bundle.docs
    assert bundle.total_snippets() >= 3

