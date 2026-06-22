"""
headroom_compress — NEXUS4 / NEXUS2 token-compression adapter.

Wraps chopratejas/headroom (PyPI: **headroom-ai**, Apache-2.0). Verified API:
    from headroom import compress
    result = compress(messages, model=..., optimize=True) -> CompressResult
    CompressResult has: .messages .tokens_before .tokens_after .tokens_saved
                        .compression_ratio .transforms_applied

Key behavior learned at runtime: headroom *protects user messages* and only
compresses tool/assistant/system content (tool outputs, logs, RAG chunks).
That matches the NEXUS use-case: compress verbose TOOL OUTPUT before it reaches
the LLM. So we wrap the blob as a `tool` message by default. Runs LOCALLY
(tiktoken counting); no network call for the compression step.

Supply-chain note: PyPI `headroom` (no -ai) is an UNRELATED package. Use
`pip install headroom-ai`.

Invariants (see REQ-2):
  - ratio in [0, 1] and tokens_after <= tokens_before (never expands)
  - local only (no network for compression)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class Compressed:
    tokens_before: int
    tokens_after: int
    tokens_saved: int
    compression_ratio: float
    transforms_applied: list
    role: str

    def to_dict(self) -> dict:
        return asdict(self)


def compress(text: str, role: str = "tool", model: str = "claude-sonnet-4-5-20250929") -> Compressed:
    """
    Compress one blob of verbose context (a tool output / log / RAG chunk).
    `role` is the message role the blob is placed under; headroom only
    compresses non-user content, so 'tool' (default), 'assistant', or 'system'
    actually compress, while 'user' is intentionally protected (ratio ~0).
    """
    from headroom import compress as hr_compress  # raises if headroom-ai absent

    messages = [
        {"role": "user", "content": "process the following context"},
        {"role": role, "content": text},
    ]
    r = hr_compress(messages, model=model, optimize=True)
    return Compressed(
        tokens_before=int(r.tokens_before),
        tokens_after=int(r.tokens_after),
        tokens_saved=int(r.tokens_saved),
        compression_ratio=round(float(r.compression_ratio), 4),
        transforms_applied=list(r.transforms_applied),
        role=role,
    )


if __name__ == "__main__":
    import sys, json
    blob = sys.stdin.read() if not sys.stdin.isatty() else (
        "[INFO] fetching https://api.example.com/v1/users page=1 status=200\n" * 80
    )
    print(json.dumps(compress(blob).to_dict(), ensure_ascii=False, indent=2))
