# aeo-kit

[![PyPI](https://img.shields.io/pypi/v/aeo-kit.svg)](https://pypi.org/project/aeo-kit/)
[![Python](https://img.shields.io/pypi/pyversions/aeo-kit.svg)](https://pypi.org/project/aeo-kit/)
[![CI](https://github.com/greymoth-jp/aeo-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/greymoth-jp/aeo-kit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Zero-Click AEO toolkit** — turn any document, file, or website into LLM-readable
Markdown + an `llms.txt` outline, then index and search it locally. A thin,
clean composition of best-in-class open-source parts; it does not reinvent
conversion, compression, or vector indexing.

```
crawl  → ingest → index → search
(site)   (md +    (turbovec) (top-k)
          llms.txt)
```

## Why
"AI Engine Optimization" (AEO/GEO) starts with getting messy real-world content
into a form a model can use. `aeo-kit` composes:

- **[markitdown](https://github.com/microsoft/markitdown)** (MIT) — PDF/DOCX/PPTX/XLSX/HTML/CSV → Markdown
- **[headroom-ai](https://github.com/chopratejas/headroom)** (Apache-2.0, optional) — compress verbose tool/RAG context 60–95%
- **[turbovec](https://github.com/RyanCodrai/turbovec)** — air-gapped quantized vector index
- a tiny zero-dependency crawler (no AGPL, no hosted API key)

Everything runs locally. No API keys required.

## Install
```bash
pip install aeo-kit            # core
pip install "aeo-kit[compress]"  # + headroom-ai for context compression
```

## CLI
```bash
# 1) crawl a site (local interlinked html or a live URL) -> markdown
aeo-crawl ./site/index.html --out build/site
aeo-crawl https://example.com --max-pages 5 --out build/site

# 2) ingest any file / folder / URL -> per-doc md + site-level llms.txt
aeo-ingest ./company_docs --out build/aeo --compress

# 3) local retrieval over the ingested docs (TF-IDF -> turbovec)
aeo-search build/site "consumption tax filing" --k 3
```

## Library
```python
from adapters import markitdown_aeo as mk
conv = mk.convert("page.html")
print(mk.aeo_extract(conv))     # llms.txt seed from the heading structure
```

## Notes
- **Crawler politeness:** HTTP mode is same-domain only, respects `robots.txt`,
  rate-limits, and is bounded by `--max-pages` / `--max-depth`.
- **Search scope:** `aeo-search` uses TF-IDF (lexical) retrieval over turbovec —
  no embedding model / network required. Swap in a sentence-transformer for
  semantic search; the turbovec layer is unchanged.
- **Compression:** `headroom-ai` protects user messages and compresses
  tool/log/RAG content; clean short prose may compress little, by design.

## Develop
```bash
pip install -e .
python experiment.py   # end-to-end real run -> poc/out/
python audit.py        # deterministic checks (exit 0 = all pass)
```

## License
MIT (this toolkit). Bundled dependencies are installed separately and retain
their own licenses — see `THIRD_PARTY_NOTICES.md`.
