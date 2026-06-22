# Third-party notices

`aeo-kit` is MIT-licensed and **composes** the following packages. They are
installed separately (not vendored), so no license obligation propagates into
this repository.

| Package | Used for | License | URL |
|---|---|---|---|
| markitdown | document → Markdown | MIT | https://github.com/microsoft/markitdown |
| turbovec | air-gapped vector index | see project | https://github.com/RyanCodrai/turbovec |
| headroom-ai | token compression (optional `[compress]`) | Apache-2.0 | https://github.com/chopratejas/headroom |
| numpy | TF-IDF vectors | BSD-3-Clause | https://github.com/numpy/numpy |

## Design note: no AGPL dependency
The "crawl a site → Markdown" step is implemented in-repo (`crawl.py`) using
only the standard library + markitdown, deliberately **avoiding AGPL-licensed
crawlers** so this MIT toolkit can be embedded and redistributed freely.
