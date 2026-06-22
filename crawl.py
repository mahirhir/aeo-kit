#!/usr/bin/env python3
"""
crawl — zero-dependency, AGPL-free site crawler (the firecrawl slot, done clean).

firecrawl is great but its core is AGPL-3.0 (license propagation if self-hosted)
and its hosted API needs a paid key. For the NEXUS1/2 "crawl a site -> markdown"
job we instead do a tiny, bounded, polite crawler over the stdlib + markitdown.
This matches the operator's own rule: avoid rented-land / prefer zero-dep.

Two scopes, same BFS:
  - LOCAL  : crawl a folder of interlinked .html files (follows relative <a href>).
             Fully offline + deterministic -> used by the AUDIT.
  - HTTP(S): same-domain only, respects robots.txt, polite delay, bounded by
             max_pages / max_depth. Outward-facing -> opt-in via a real URL.

Each fetched page -> markitdown -> Markdown; the set -> one site-level llms.txt.

Run:
    python crawl.py poc/samples/site/index.html --out build/crawl
    python crawl.py https://example.com --max-pages 5 --out build/crawl
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from adapters import markitdown_aeo as mk  # noqa: E402

_HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _links_in(html: str) -> list[str]:
    return _HREF_RE.findall(html)


# ---------------- LOCAL scope ----------------
def crawl_local(seed: Path, max_pages: int = 50) -> list[tuple[str, str]]:
    """BFS over interlinked local .html files. Returns [(label, html)]."""
    seed = seed.resolve()
    root = seed.parent
    seen, queue, pages = set(), [seed], []
    while queue and len(pages) < max_pages:
        f = queue.pop(0)
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        html = f.read_text(encoding="utf-8", errors="replace")
        pages.append((str(f.relative_to(root)).replace("\\", "/"), html))
        for href in _links_in(html):
            if _is_url(href) or href.startswith("#") or href.startswith("mailto:"):
                continue  # external / anchors / mailto are out of scope
            target = (f.parent / href.split("#")[0]).resolve()
            # stay within the seed's directory subtree
            if root in target.parents or target.parent == root:
                if target not in seen:
                    queue.append(target)
    return pages


# ---------------- HTTP scope ----------------
def crawl_http(seed: str, max_pages: int = 10, max_depth: int = 2,
               delay: float = 1.0) -> list[tuple[str, str]]:
    """Polite same-domain BFS. Respects robots.txt; bounded; rate-limited."""
    base = urllib.parse.urlparse(seed)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{base.scheme}://{base.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        pass  # no robots -> allowed, but still bounded + polite

    seen, queue, pages = set(), [(seed, 0)], []
    ua = "aeo-ingest-crawler/1.0 (+polite; bounded)"
    while queue and len(pages) < max_pages:
        url, depth = queue.pop(0)
        if url in seen or depth > max_depth:
            continue
        seen.add(url)
        if not rp.can_fetch(ua, url):
            continue  # robots.txt disallows
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
                if "html" not in r.headers.get("Content-Type", "html"):
                    continue
                html = r.read().decode("utf-8", errors="replace")
        except Exception:
            continue
        pages.append((url, html))
        time.sleep(delay)  # politeness
        for href in _links_in(html):
            nxt = urllib.parse.urljoin(url, href.split("#")[0])
            p = urllib.parse.urlparse(nxt)
            if p.scheme in ("http", "https") and p.netloc == base.netloc and nxt not in seen:
                queue.append((nxt, depth + 1))
    return pages


def crawl(seed: str, out_dir: Path, max_pages: int = 50, max_depth: int = 2) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    if _is_url(seed):
        pages = crawl_http(seed, max_pages=max_pages, max_depth=max_depth)
        scope = "http"
    else:
        pages = crawl_local(Path(seed), max_pages=max_pages)
        scope = "local"

    docs, index = [], ["# Site AEO Index", "", f"> {len(pages)} page(s) crawled from `{seed}` ({scope})", ""]
    for label, html in pages:
        tmp = out_dir / ("_page_" + re.sub(r"[^a-zA-Z0-9]+", "_", label)[:60] + ".html")
        tmp.write_text(html, encoding="utf-8")
        conv = mk.convert(tmp)
        tmp.unlink(missing_ok=True)
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", label)[:60].strip("_") or "page"
        (out_dir / f"{slug}.md").write_text(conv.markdown, encoding="utf-8")
        index.append(f"- **{conv.title}** — `{label}` ({conv.n_headings} headings)")
        docs.append({"label": label, "title": conv.title, "headings": conv.n_headings})

    (out_dir / "llms.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    return {"seed": seed, "scope": scope, "n_pages": len(pages),
            "out_dir": str(out_dir), "pages": [d["label"] for d in docs], "docs": docs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="crawl", description="zero-dep AGPL-free site crawler")
    ap.add_argument("seed", help="local .html file (folder crawl) or http(s) URL")
    ap.add_argument("--out", default="build/crawl")
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--max-depth", type=int, default=2)
    args = ap.parse_args(argv)
    res = crawl(args.seed, Path(args.out), max_pages=args.max_pages, max_depth=args.max_depth)
    print(f"crawled {res['n_pages']} page(s) [{res['scope']}] -> {res['out_dir']}")
    for d in res["docs"]:
        print(f"  - {d['title']}  ({d['headings']} headings)  [{d['label']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
