"""
turbovec_rag — NEXUS4 air-gap RAG memory adapter.

Wraps RyanCodrai/turbovec (TurboQuantIndex): an online, quantized vector
index with no train step, built for local/air-gapped RAG. Real API verified
at runtime:
    TurboQuantIndex(dim, bit_width=4)
    .add(vectors: float32[n, dim]) -> indices
    .prepare()                      # warm caches
    .search(queries, k, mask=None) -> (ids, distances)

Invariants (see REQ-3):
  - online: add then search with no train step
  - search returns up to k ids per query, ids in valid range
  - local only (no network)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

try:
    from turbovec import TurboQuantIndex
except Exception as e:  # pragma: no cover
    TurboQuantIndex = None
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None


@dataclass
class SearchResult:
    n_indexed: int
    dim: int
    bit_width: int
    query_count: int
    k: int
    ids: list
    self_recall_at_k: float   # fraction whose own id is in top-k (correct metric for an approximate quantized index)
    self_recall_at_1: float   # stricter: own id at rank 1 (quantization makes this < 1.0; reported for honesty)

    def to_dict(self) -> dict:
        return asdict(self)


class RagMemory:
    """Thin air-gap RAG memory over TurboQuantIndex."""

    def __init__(self, dim: int, bit_width: int = 4):
        if TurboQuantIndex is None:
            raise RuntimeError(f"turbovec not importable: {_IMPORT_ERROR!r}")
        self.dim = dim
        self.bit_width = bit_width
        self.index = TurboQuantIndex(dim, bit_width=bit_width)
        self._n = 0

    def add(self, vectors: np.ndarray) -> int:
        v = np.ascontiguousarray(vectors, dtype=np.float32)
        self.index.add(v)
        self._n += v.shape[0]
        return self._n

    def prepare(self):
        self.index.prepare()

    def search(self, queries: np.ndarray, k: int):
        q = np.ascontiguousarray(queries, dtype=np.float32)
        return self.index.search(q, k)


def _normalize_ids(raw):
    """turbovec.search returns a (distances, ids) tuple. Return list-of-lists of ids."""
    ids = raw[1] if isinstance(raw, tuple) else raw
    arr = np.asarray(ids)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr.astype(int).tolist()


def poc(n: int = 256, dim: int = 64, bit_width: int = 4, k: int = 10, seed: int = 7) -> SearchResult:
    """Self-recall PoC: index n random vectors, query with the same vectors.
    For an approximate (quantized) index the right sanity metric is recall@k
    (own id is in the top-k); recall@1 is reported too but is expected < 1.0."""
    rng = np.random.default_rng(seed)
    corpus = rng.standard_normal((n, dim)).astype(np.float32)
    mem = RagMemory(dim, bit_width=bit_width)
    mem.add(corpus)
    mem.prepare()
    qn = min(32, n)
    raw = mem.search(corpus[:qn], k=k)
    ids = _normalize_ids(raw)
    hit_k = sum(1 for i, row in enumerate(ids) if i in row)
    hit_1 = sum(1 for i, row in enumerate(ids) if row and row[0] == i)
    return SearchResult(
        n_indexed=len(mem.index),
        dim=dim,
        bit_width=bit_width,
        query_count=qn,
        k=k,
        ids=ids[:3],
        self_recall_at_k=round(hit_k / qn, 3),
        self_recall_at_1=round(hit_1 / qn, 3),
    )


if __name__ == "__main__":
    import json
    print(json.dumps(poc().to_dict(), ensure_ascii=False, indent=2))
