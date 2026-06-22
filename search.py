#!/usr/bin/env python3
"""
search — local retrieval over ingested docs, using turbovec as the index.

Closes the NEXUS1+NEXUS4 loop and makes turbovec earn its place in the real
pipeline (not just a synthetic self-recall test):

    markdown docs --chunk--> TF-IDF vectors (numpy, zero extra dep)
                                   --> turbovec TurboQuantIndex --> top-k query

Honest scope: TF-IDF is *lexical* retrieval (term overlap), not neural-semantic
search. We use it because it needs no embedding model / no network / no creds,
while still proving turbovec works as the air-gap index over real text. Swap in
a sentence-transformer later for semantics; the turbovec layer is unchanged.

Run:
    python search.py build/crawl_local "consumption tax filing"
    python search.py build/aeo2 "invoice accuracy" --k 3
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from adapters.turbovec_rag import RagMemory, _normalize_ids  # noqa: E402

_WORD = re.compile(r"[a-z0-9]+")
MAX_VOCAB = 256


def _round_up_8(n: int) -> int:
    """turbovec's TurboQuantIndex requires dim to be a positive multiple of 8."""
    return max(8, ((n + 7) // 8) * 8)


def _tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def load_corpus(src: Path) -> list[tuple[str, str]]:
    """Load (label, chunk_text) from .md files in a directory (recursive)."""
    chunks: list[tuple[str, str]] = []
    files = sorted(src.rglob("*.md")) if src.is_dir() else [src]
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        # chunk by blank-line-separated paragraphs; keep non-trivial ones
        for i, para in enumerate(re.split(r"\n\s*\n", text)):
            p = para.strip()
            if len(p) >= 12:
                chunks.append((f"{f.stem}#{i}", p))
    return chunks


class TfidfSpace:
    """Deterministic TF-IDF vectorizer capped to MAX_VOCAB terms by doc-freq."""

    def __init__(self, corpus_texts: list[str]):
        df: dict[str, int] = {}
        for t in corpus_texts:
            for w in set(_tokenize(t)):
                df[w] = df.get(w, 0) + 1
        n = max(1, len(corpus_texts))
        # pick most frequent terms (stable: by -df then term) -> fixed dim
        terms = sorted(df.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_VOCAB]
        self.vocab = {w: i for i, (w, _) in enumerate(terms)}
        # pad dim to a multiple of 8 (turbovec requirement); extra dims stay zero
        self._dim = _round_up_8(len(self.vocab))
        self.idf = np.zeros(self._dim, dtype=np.float32)
        for w, i in self.vocab.items():
            self.idf[i] = math.log((1 + n) / (1 + df[w])) + 1.0

    @property
    def dim(self) -> int:
        return self._dim

    def vec(self, text: str) -> np.ndarray:
        v = np.zeros(self._dim, dtype=np.float32)
        toks = _tokenize(text)
        if not toks:
            return v
        for w in toks:
            j = self.vocab.get(w)
            if j is not None:
                v[j] += 1.0
        v = v / len(toks)          # term frequency
        v = v * self.idf           # * idf
        nrm = np.linalg.norm(v)
        return v / nrm if nrm > 0 else v


class DocIndex:
    def __init__(self, corpus: list[tuple[str, str]]):
        self.labels = [c[0] for c in corpus]
        self.texts = [c[1] for c in corpus]
        self.space = TfidfSpace(self.texts)
        mat = np.vstack([self.space.vec(t) for t in self.texts]).astype(np.float32)
        self.mem = RagMemory(self.space.dim, bit_width=4)
        self.mem.add(mat)
        self.mem.prepare()

    def query(self, q: str, k: int = 5) -> list[tuple[str, str]]:
        qv = self.space.vec(q).reshape(1, -1).astype(np.float32)
        ids = _normalize_ids(self.mem.search(qv, k=min(k, len(self.labels))))[0]
        out = []
        for i in ids:
            if 0 <= i < len(self.labels):
                snippet = " ".join(self.texts[i].split())[:90]
                out.append((self.labels[i], snippet))
        return out


def build(src: Path) -> DocIndex:
    corpus = load_corpus(src)
    if not corpus:
        raise SystemExit(f"no .md chunks under {src} (run crawl.py / aeo_ingest.py first)")
    return DocIndex(corpus)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="search", description="turbovec retrieval over ingested docs")
    ap.add_argument("src", help="directory of .md files (crawl/ingest output)")
    ap.add_argument("query", help="search query")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args(argv)
    idx = build(Path(args.src))
    print(f"indexed {len(idx.labels)} chunks (dim={idx.space.dim}) via turbovec")
    print(f'query: "{args.query}"')
    for rank, (label, snip) in enumerate(idx.query(args.query, k=args.k), 1):
        print(f"  {rank}. {label}  —  {snip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
