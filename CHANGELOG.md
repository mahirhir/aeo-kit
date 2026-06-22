# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — 2026-06-23

First release.

### Added
- `aeo-crawl` — zero-dependency, AGPL-free site crawler. Local interlinked-HTML
  mode (offline, deterministic) and HTTP mode (same-domain, `robots.txt`-aware,
  rate-limited, bounded by `--max-pages` / `--max-depth`).
- `aeo-ingest` — convert any file / folder / URL to per-document Markdown plus a
  site-level `llms.txt` outline via [markitdown]. Optional `--compress` reports
  [headroom-ai] token economics on the ingested context.
- `aeo-search` — local TF-IDF retrieval over a [turbovec] `TurboQuantIndex`.
- Library adapters under `adapters/` for each composed tool.
- `experiment.py` (end-to-end real run) and `audit.py` (deterministic checks).

### Notes
- Composes markitdown (MIT) + turbovec + headroom-ai (Apache-2.0). Local, no API
  keys. MIT licensed; dependencies retain their own licenses.

[markitdown]: https://github.com/microsoft/markitdown
[headroom-ai]: https://github.com/chopratejas/headroom
[turbovec]: https://github.com/RyanCodrai/turbovec
[0.1.0]: https://github.com/greymoth-jp/aeo-kit/releases/tag/v0.1.0
