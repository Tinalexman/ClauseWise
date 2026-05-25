"""
Build BM25 and ChromaDB vector indexes from the evidence corpus.

Usage:
    python -m src.retrieval.build_index --corpus data/evidence_corpus/ --output data/indexes/
"""

import argparse
import json
import pickle
from pathlib import Path


def build_indexes(corpus_dir: str, output_dir: str) -> None:
    corpus_path = Path(corpus_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    docs = _load_corpus(corpus_path)
    print(f"Loaded {len(docs)} evidence items")

    _build_bm25_index(docs, output_path)
    _build_dense_index(docs, output_path)


def _load_corpus(corpus_path: Path) -> list[dict]:
    docs = []
    for jsonl_file in corpus_path.glob("*.jsonl"):
        with jsonl_file.open() as f:
            for line in f:
                docs.append(json.loads(line))
    return docs


def _build_bm25_index(docs: list[dict], output_path: Path) -> None:
    """Tokenise corpus and serialise BM25Okapi to bm25_index.pkl."""
    raise NotImplementedError


def _build_dense_index(docs: list[dict], output_path: Path) -> None:
    """Embed corpus with MiniLM-L6-v2 and upsert into ChromaDB collection."""
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    build_indexes(args.corpus, args.output)
