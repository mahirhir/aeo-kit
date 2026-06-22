"""
experiment.py — end-to-end real-run smoke for the NEXUS OSS integration lab.

LOOP_CONSTRAINTS #12: every pipeline must really run and emit real output,
not just assert. Tools that are not installed are reported HONESTLY as
skipped-with-reason (no fake "operated" stamps).

Run:  .venv/Scripts/python.exe experiment.py
Emits: poc/out/*.llms.txt , poc/out/*.md , poc/out/results.json
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "poc" / "out"
OUT.mkdir(parents=True, exist_ok=True)
SAMPLES = ROOT / "poc" / "samples"

results: dict = {"tools": {}}


def record(tool: str, status: str, detail: dict | None = None):
    results["tools"][tool] = {"status": status, **(detail or {})}


# ---- NEXUS1: markitdown AEO (must really run) ----
def run_markitdown():
    from adapters import markitdown_aeo as m

    runs = []
    for sample in ["acme_product.html", "pricing.csv"]:
        c = m.convert(SAMPLES / sample)
        llms = m.aeo_extract(c, base_url="https://example.com")
        md_path = OUT / (Path(sample).stem + ".md")
        llms_path = OUT / (Path(sample).stem + ".llms.txt")
        md_path.write_text(c.markdown, encoding="utf-8")
        llms_path.write_text(llms, encoding="utf-8")
        runs.append({
            "sample": sample,
            "title": c.title,
            "n_chars": c.n_chars,
            "n_headings": c.n_headings,
            "md_out": str(md_path.relative_to(ROOT)),
            "llms_out": str(llms_path.relative_to(ROOT)),
            "llms_lines": llms.count("\n"),
        })
    record("markitdown", "ran", {"runs": runs})


# ---- NEXUS4/2: headroom compression (run if installed) ----
def run_headroom():
    from adapters import headroom_compress as h

    # realistic verbose tool output (the kind headroom is meant to compress)
    blob = (
        "[2026-06-22 12:00:01] INFO  fetching https://api.example.com/v1/users "
        "page=1 ...\n" * 60
        + "DEBUG payload: " + json.dumps({"users": [{"id": i, "name": f"user{i}",
          "active": True, "meta": {"plan": "team", "seats": 5}} for i in range(40)]})
    )
    c = h.compress(blob)
    (OUT / "headroom_sample.txt").write_text(blob, encoding="utf-8")
    record("headroom", "ran", c.to_dict())


# ---- NEXUS4: turbovec RAG index (real self-recall PoC) ----
def run_turbovec():
    from adapters import turbovec_rag as t
    res = t.poc(n=256, dim=64, bit_width=4, k=10)
    record("turbovec", "ran", res.to_dict())


def main() -> int:
    # markitdown is the load-bearing PoC: failure here is a real failure.
    try:
        run_markitdown()
    except Exception:
        record("markitdown", "FAILED", {"trace": traceback.format_exc()})

    # headroom / turbovec are best-effort: not-installed => honest skip.
    for name, fn in (("headroom", run_headroom), ("turbovec", run_turbovec)):
        try:
            fn()
        except ModuleNotFoundError as e:
            record(name, "skipped:not-installed", {"reason": str(e)})
        except Exception:
            record(name, "ERROR", {"trace": traceback.format_exc()})

    (OUT / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    # exit non-zero only if the load-bearing tool failed
    return 1 if results["tools"].get("markitdown", {}).get("status") == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
