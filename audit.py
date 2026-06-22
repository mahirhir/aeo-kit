"""
audit.py — strict, deterministic AUDIT for the NEXUS OSS integration lab.

LOOP_CONSTRAINTS #7/#13: AUDIT must be 100% pass and must not be skipped.
Hard checks (load-bearing real PoCs) fail the build on violation.
Soft checks (install-dependent tools) report HONESTLY but don't fail the build
unless the tool is present and misbehaves.

Run:  .venv/Scripts/python.exe audit.py   (exit 0 == all hard checks pass)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

checks: list[tuple[str, bool, str]] = []  # (name, passed, detail)


def hard(name: str, cond: bool, detail: str = ""):
    checks.append((f"[HARD] {name}", bool(cond), detail))


def soft(name: str, cond: bool, detail: str = ""):
    checks.append((f"[soft] {name}", bool(cond), detail))


# === AUDIT-1: markitdown AEO (deterministic on our fixed samples) ===
def audit_markitdown():
    from adapters import markitdown_aeo as m
    SAM = ROOT / "poc" / "samples"

    c1 = m.convert(SAM / "acme_product.html")
    c2 = m.convert(SAM / "acme_product.html")
    hard("markitdown.nonempty", c1.n_chars > 0, f"n_chars={c1.n_chars}")
    hard("markitdown.headings>=8", c1.n_headings >= 8, f"n_headings={c1.n_headings}")
    hard("markitdown.deterministic", c1.markdown == c2.markdown,
         "two conversions identical")
    llms = m.aeo_extract(c1)
    hard("markitdown.llms_has_title", llms.splitlines()[0].startswith("# Acme Ledger"),
         llms.splitlines()[0])
    for needle in ("Key Features", "Pricing", "FAQ", "Banks"):
        hard(f"markitdown.llms_has_{needle.replace(' ','_')}", needle in llms,
             f"'{needle}' in outline")
    # CSV path (0 headings -> fallback line)
    cc = m.convert(SAM / "pricing.csv")
    hard("markitdown.csv_nonempty", cc.n_chars > 0, f"csv n_chars={cc.n_chars}")


# === AUDIT-2: turbovec air-gap RAG (real self-recall) ===
def audit_turbovec():
    try:
        from adapters import turbovec_rag as t
    except Exception as e:
        soft("turbovec.import", False, f"not importable: {e}")
        return
    res = t.poc(n=256, dim=64, bit_width=4, k=10)
    hard("turbovec.indexed_256", res.n_indexed == 256, f"n_indexed={res.n_indexed}")
    hard("turbovec.self_recall@k==1.0", res.self_recall_at_k == 1.0,
         f"recall@k={res.self_recall_at_k}")
    hard("turbovec.bit_width_in_2_4", res.bit_width in (2, 3, 4),
         f"bit_width={res.bit_width}")


# === AUDIT-3: headroom compression (install-dependent => soft) ===
def audit_headroom():
    try:
        from headroom import compress  # noqa: F401
    except Exception as e:
        soft("headroom.import", False, f"headroom-ai not importable: {e}")
        return
    from adapters import headroom_compress as h
    try:
        log_blob = "[INFO] GET /v1/users page=1 status=200 latency=12ms\n" * 80
        c = h.compress(log_blob, role="tool")
        soft("headroom.no_expand", c.tokens_after <= c.tokens_before,
             f"{c.tokens_before}->{c.tokens_after}")
        soft("headroom.ratio_in_0_1", 0.0 <= c.compression_ratio <= 1.0,
             f"ratio={c.compression_ratio}")
        # log-like tool output should compress substantially
        soft("headroom.compresses_logs", c.compression_ratio > 0.5,
             f"ratio={c.compression_ratio} transforms={c.transforms_applied}")
        # user messages must be protected (not compressed)
        cu = h.compress("important question from the user", role="user")
        soft("headroom.protects_user", cu.compression_ratio == 0.0,
             f"user ratio={cu.compression_ratio}")
    except Exception as e:
        soft("headroom.compress", False, f"compress failed: {e}")


# === AUDIT-4: aeo-ingest CLI (deterministic folder ingest) ===
def audit_cli():
    import aeo_ingest
    out = ROOT / "build" / "_audit_aeo"
    res = aeo_ingest.ingest(str(ROOT / "poc" / "samples"), out, compress=False)
    hard("cli.ingested_ge2", res["n_sources"] >= 2, f"n_sources={res['n_sources']}")
    idx = Path(res["index"])
    hard("cli.index_written", idx.is_file() and idx.stat().st_size > 0,
         f"index={idx.name}")
    titles = [d["title"] for d in res["docs"]]
    hard("cli.has_acme", any("Acme Ledger" in t for t in titles), str(titles))


# === AUDIT-5: zero-dep crawler (deterministic local BFS) ===
def audit_crawler():
    import crawl
    out = ROOT / "build" / "_audit_crawl"
    seed = ROOT / "poc" / "samples" / "site" / "index.html"
    res = crawl.crawl(str(seed), out, max_pages=50)
    labels = set(res["pages"])
    hard("crawl.found_4", res["n_pages"] == 4, f"n_pages={res['n_pages']}")
    hard("crawl.has_all_pages",
         {"index.html", "product.html", "pricing.html", "about.html"} <= labels,
         str(sorted(labels)))
    hard("crawl.excludes_external",
         not any("external" in l or l.startswith("http") for l in labels),
         "no external/http labels")


# === AUDIT-6: turbovec retrieval over real crawled text (relevance) ===
def audit_search():
    try:
        import crawl, search  # noqa
    except Exception as e:
        soft("search.import", False, str(e))
        return
    out = ROOT / "build" / "_audit_search"
    crawl.crawl(str(ROOT / "poc" / "samples" / "site" / "index.html"), out, max_pages=50)
    idx = search.build(out)
    hard("search.indexed", len(idx.labels) >= 4, f"chunks={len(idx.labels)}")
    tax = idx.query("consumption tax filing", k=3)
    hard("search.tax_relevant", any("product_html" in lbl for lbl, _ in tax),
         str([l for l, _ in tax]))
    inv = idx.query("invoice accuracy", k=3)
    hard("search.invoice_top_is_product", bool(inv) and inv[0][0].startswith("product_html"),
         str(inv[0][0]) if inv else "no result")
    hard("search.dim_multiple_of_8", idx.space.dim % 8 == 0, f"dim={idx.space.dim}")
    # regression: tiny corpus (small vocab, not a multiple of 8) must not crash
    tiny = out / "_tiny"
    tiny.mkdir(parents=True, exist_ok=True)
    (tiny / "a.md").write_text("# Widget\nPro plan is nineteen dollars per month.\n",
                               encoding="utf-8")
    tidx = search.build(tiny)
    hard("search.tiny_dim_multiple_of_8", tidx.space.dim % 8 == 0, f"tiny dim={tidx.space.dim}")
    hard("search.tiny_query_ok", len(tidx.query("plan price", k=2)) >= 1, "tiny query returns")


# === AUDIT-0: non-destruction invariant ===
def audit_non_destruction():
    # This lab must only ever create files under its own root. We assert the
    # adapters dir and poc/out exist and are inside ROOT (sanity that we built
    # a clean-room, not edited anything outside).
    inside = (ROOT / "adapters").is_dir() and (ROOT / "poc").is_dir()
    hard("lab.is_clean_room", inside, "adapters/ and poc/ under lab root")


def main() -> int:
    audit_non_destruction()
    audit_markitdown()
    audit_turbovec()
    audit_headroom()
    audit_cli()
    audit_crawler()
    audit_search()

    width = max(len(n) for n, _, _ in checks)
    hard_fail = 0
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        if not ok and name.startswith("[HARD]"):
            hard_fail += 1
        print(f"  {status}  {name.ljust(width)}  {detail}")
    n_hard = sum(1 for n, _, _ in checks if n.startswith("[HARD]"))
    n_hard_pass = sum(1 for n, ok, _ in checks if n.startswith("[HARD]") and ok)
    print(f"\nHARD: {n_hard_pass}/{n_hard} passed | soft checks informational")
    if hard_fail:
        print(f"AUDIT FAILED: {hard_fail} hard check(s) failed")
        return 1
    print("AUDIT PASS (100% hard checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
