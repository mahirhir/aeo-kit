"""
markitdown_aeo — NEXUS1 (Zero-Click AEO) ingest adapter.

Wraps microsoft/markitdown (MIT) as the document->markdown normalizer, then
derives a naive `llms.txt` candidate from the heading structure. Clean-room:
we do NOT reinvent file conversion (YAGNI); markitdown is the engine.

Invariants (see REQ-1):
  - deterministic: same input -> same output
  - local only: markitdown core needs no network/API
  - convert() output non-empty for supported formats
  - aeo_extract() llms.txt has a title line + at least the H1/H2 outline
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    from markitdown import MarkItDown
except Exception as e:  # pragma: no cover - surfaced by PoC/audit honestly
    MarkItDown = None
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


@dataclass
class Converted:
    source: str
    title: str
    markdown: str
    n_chars: int
    n_headings: int

    def to_dict(self) -> dict:
        return asdict(self)


def _engine() -> "MarkItDown":
    if MarkItDown is None:
        raise RuntimeError(
            f"markitdown not importable: {_IMPORT_ERROR!r}. "
            f"Install with: pip install 'markitdown[docx,pptx,xlsx,pdf]'"
        )
    return MarkItDown(enable_plugins=False)


def convert(path: str | Path) -> Converted:
    """Convert any supported document to Markdown via markitdown."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    res = _engine().convert(str(p))
    md = (res.text_content or "").strip()
    headings = _HEADING_RE.findall(md)
    # markitdown exposes .title for some formats; fall back to first H1 or stem
    title = getattr(res, "title", None) or ""
    if not title:
        h1 = next((t for lvl, t in headings if len(lvl) == 1), None)
        title = h1 or p.stem
    return Converted(
        source=p.name,
        title=title.strip(),
        markdown=md,
        n_chars=len(md),
        n_headings=len(headings),
    )


def aeo_extract(conv: Converted, base_url: str = "") -> str:
    """
    Build a naive llms.txt candidate from heading structure.
    Format follows the llms.txt convention: '# Title' then a short outline.
    This is the NEXUS1 'Zero-Click AEO' seed, not a finished spec.
    """
    headings = _HEADING_RE.findall(conv.markdown)
    lines: list[str] = [f"# {conv.title}", ""]
    lines.append(f"> Source: {conv.source}"
                 + (f" ({base_url})" if base_url else ""))
    lines.append("")
    lines.append("## Outline")
    for lvl, text in headings:
        depth = len(lvl)
        if depth > 3:
            continue  # AEO outline keeps top 3 levels
        indent = "  " * (depth - 1)
        lines.append(f"{indent}- {text.strip()}")
    if len(headings) == 0:
        # no headings: emit a single section from the first non-empty line
        first = next((ln.strip() for ln in conv.markdown.splitlines() if ln.strip()), "")
        lines.append(f"- {first[:120]}")
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    import sys, json
    c = convert(sys.argv[1])
    print(json.dumps({k: v for k, v in c.to_dict().items() if k != "markdown"},
                     ensure_ascii=False, indent=2))
    print("--- llms.txt candidate ---")
    print(aeo_extract(c))
