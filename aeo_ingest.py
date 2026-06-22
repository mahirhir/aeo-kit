#!/usr/bin/env python3
"""
aeo-ingest — Zero-Click AEO ingest CLI (NEXUS1 value as a shippable artifact).

Composes proven OSS parts (markitdown + headroom-ai) into one usable tool:

    any file / folder / URL  --markitdown-->  clean Markdown (per source)
                                   |
                                   +--> site-level llms.txt index (AEO seed)
                                   +--[optional --compress]--> headroom token economics

Why this exists: turning company documents and pages into LLM-readable Markdown
+ an llms.txt outline is the front door of "AI Engine Optimization". We do not
reinvent conversion (markitdown, MIT) or compression (headroom-ai, Apache-2.0);
we compose them.

Local, no API keys. URL mode does a plain HTTP GET (no creds). Run:
    python aeo_ingest.py <file|folder|url> [--out DIR] [--compress] [--json]

Examples:
    python aeo_ingest.py poc/samples/acme_product.html
    python aeo_ingest.py ./company_docs --out build/aeo --compress
    python aeo_ingest.py https://example.com --out build/aeo
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from adapters import markitdown_aeo as mk  # noqa: E402

SUPPORTED = {".html", ".htm", ".pdf", ".docx", ".pptx", ".xlsx", ".csv",
             ".json", ".xml", ".txt", ".md"}


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _fetch_url(url: str) -> Path:
    """GET a URL into a temp .html file (no creds, plain urllib)."""
    req = urllib.request.Request(url, headers={"User-Agent": "aeo-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 (explicit http(s) only)
        data = r.read()
    tmp = Path(tempfile.gettempdir()) / ("aeo_" + str(abs(hash(url)) % 10**8) + ".html")
    tmp.write_bytes(data)
    return tmp


def _gather(target: str) -> list[tuple[str, Path]]:
    """Return (label, path) pairs to ingest."""
    if _is_url(target):
        return [(target, _fetch_url(target))]
    p = Path(target)
    if p.is_dir():
        return sorted(
            (str(f.relative_to(p)), f)
            for f in p.rglob("*")
            if f.is_file() and f.suffix.lower() in SUPPORTED
        )
    if p.is_file():
        return [(p.name, p)]
    raise FileNotFoundError(target)


def ingest(target: str, out_dir: Path, compress: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    items = _gather(target)
    if not items:
        raise SystemExit(f"no supported files under {target} (supported: {sorted(SUPPORTED)})")

    docs = []
    index_lines = ["# AEO Ingest Index", "", f"> {len(items)} source(s) from `{target}`", ""]
    for label, path in items:
        conv = mk.convert(path)
        slug = Path(label).stem.replace("/", "_").replace("\\", "_")
        md_path = out_dir / f"{slug}.md"
        llms_path = out_dir / f"{slug}.llms.txt"
        md_path.write_text(conv.markdown, encoding="utf-8")
        llms_path.write_text(mk.aeo_extract(conv, base_url=label if _is_url(label) else ""),
                             encoding="utf-8")
        index_lines.append(f"- **{conv.title}** — `{label}` "
                           f"({conv.n_headings} headings, {conv.n_chars} chars)")
        docs.append({"label": label, "title": conv.title, "chars": conv.n_chars,
                     "headings": conv.n_headings, "md": str(md_path.relative_to(out_dir)),
                     "llms": str(llms_path.relative_to(out_dir))})

    index_path = out_dir / "llms.txt"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    result = {"target": target, "n_sources": len(items),
              "out_dir": str(out_dir), "index": str(index_path), "docs": docs}

    if compress:
        result["compression"] = _compress_bundle(docs, out_dir)
    return result


def _compress_bundle(docs: list[dict], out_dir: Path) -> dict:
    """Show headroom token economics on the concatenated ingested markdown
    (the realistic 'retrieved RAG context' a NEXUS would feed an LLM)."""
    try:
        from adapters import headroom_compress as hr
    except Exception as e:  # headroom-ai not installed
        return {"status": "skipped", "reason": str(e)}
    bundle = "\n\n".join((out_dir / d["md"]).read_text(encoding="utf-8") for d in docs)
    c = hr.compress(bundle, role="tool")
    return {"status": "ran", **c.to_dict()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="aeo-ingest", description="Zero-Click AEO ingest")
    ap.add_argument("target", help="file, folder, or http(s) URL")
    ap.add_argument("--out", default="build/aeo", help="output dir (relative to cwd)")
    ap.add_argument("--compress", action="store_true", help="report headroom token economics")
    ap.add_argument("--json", action="store_true", help="print full JSON result")
    args = ap.parse_args(argv)

    res = ingest(args.target, Path(args.out), compress=args.compress)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"ingested {res['n_sources']} source(s) -> {res['out_dir']}")
        print(f"  index: {res['index']}")
        for d in res["docs"]:
            print(f"  - {d['title']}  ({d['headings']} headings)")
        if "compression" in res:
            c = res["compression"]
            if c.get("status") == "ran":
                print(f"  context compression: {c['tokens_before']} -> {c['tokens_after']} "
                      f"tokens (ratio {c['compression_ratio']})")
            else:
                print(f"  context compression: skipped ({c.get('reason')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
