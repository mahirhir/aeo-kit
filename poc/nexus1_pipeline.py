"""
nexus1_pipeline — capstone PoC: compose two world-class OSS parts end-to-end.

This demonstrates the CC_Portfolio_Master_Architecture thesis directly: CC does
not reinvent conversion/compression; it *composes* markitdown + headroom-ai.

Pipeline (NEXUS1 "Zero-Click AEO" ingest, with NEXUS4 compression):
    document  --markitdown-->  Markdown  --aeo_extract-->  llms.txt seed
                                   |
                                   +--headroom(role=tool)--> compressed context
                                                              (token economics)

Real, local, no network, no paid API. Run:
    .venv/Scripts/python.exe poc/nexus1_pipeline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import markitdown_aeo as mk      # noqa: E402
from adapters import headroom_compress as hr   # noqa: E402


def run(doc: Path) -> dict:
    # Stage 1 — markitdown: any document -> clean Markdown
    conv = mk.convert(doc)
    # Stage 2 — derive llms.txt seed for AEO
    llms = mk.aeo_extract(conv, base_url="https://example.com")
    # Stage 3 — headroom: compress the ingested markdown as retrieved CONTEXT
    #           (this is how a NEXUS would shrink RAG context before the LLM)
    comp = hr.compress(conv.markdown, role="tool")
    return {
        "document": doc.name,
        "stage1_markitdown": {
            "title": conv.title,
            "markdown_chars": conv.n_chars,
            "headings": conv.n_headings,
        },
        "stage2_aeo": {
            "llms_txt_lines": llms.count("\n"),
            "llms_txt_preview": llms.splitlines()[:4],
        },
        "stage3_headroom": {
            "tokens_before": comp.tokens_before,
            "tokens_after": comp.tokens_after,
            "tokens_saved": comp.tokens_saved,
            "compression_ratio": comp.compression_ratio,
            "transforms": comp.transforms_applied,
        },
    }


if __name__ == "__main__":
    doc = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "poc" / "samples" / "acme_product.html"
    out = run(doc)
    print(json.dumps(out, ensure_ascii=False, indent=2))
