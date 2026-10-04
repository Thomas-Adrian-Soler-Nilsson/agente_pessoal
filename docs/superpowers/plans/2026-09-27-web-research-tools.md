# Web Research Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make internet search, single-page reading, deep research, and technical search return ranked, source-attributed results with clear partial and failure states.

**Architecture:** Split discovery, URL validation, extraction, and result formatting into focused functions in tools/web_search.py. Expose normalized JSON-compatible outcomes to LocalToolExecutor and add a distinct web_open tool; keep research independent from the authenticated Chrome extension.

**Tech Stack:** Python 3.12, ddgs, requests, trafilatura, existing compatible tool-call schemas.

**Spec:** docs/superpowers/specs/2026-09-27-browser-tools-design.md

## Global Constraints

- Keep title, canonical/final URL, source domain, snippet/content, and status attached to each source.
- Distinguish empty results, backend failure, timeout, HTTP rejection, blocked pages, and extraction failure.
- Preserve partial results and stable search ranking; never use thread completion order as relevance order.
- Deep research and code search return source-level evidence; the model synthesizes claims from those sources.
- Keep public web research usable when the Chrome extension is unavailable.
- Reject non-HTTP(S), embedded credentials, localhost, and private/reserved destinations; revalidate redirects before following them.

## Review Focus

- Search provider throws or times out: return a backend failure status, not a false “no results”.
- A search result redirects to localhost/private/reserved address: reject it before fetching and return a blocked destination status.
- A URL redirects or becomes invalid: retain the final URL/status and avoid duplicate canonical sources.
- Some pages extract while others fail: return partial results with per-source status.
- A page is reachable but JavaScript-only or blocked: report extraction failure distinctly from an empty page.
- A code query names a package or documentation topic: preserve the PyPI fast path while attributing official documentation/repository sources.

---

### Task 1: Define normalized source and search outcomes

**Files:**
- Create: tools/web_research.py
- Modify: tools/web_search.py

**Interfaces:**
- SearchSource mapping: title, url, domain, snippet, status, content, error_code.
- SearchOutcome mapping: status, query, sources, backend, errors.
- discover_sources(query: str, max_results: int = 5) -> SearchOutcome.

- [ ] Define JSON-compatible result construction and status/error vocabulary in tools/web_research.py.
- [ ] Move DDGS result normalization and URL validation into discover_sources; retain original rank after concurrent validation.
- [ ] Preserve snippets when provided by the backend, final redirected URLs, and canonical-URL deduplication.
- [ ] Report backend failure, no hits, invalid URLs, and partial validation as different outcome states.
- [ ] Review compatibility for existing imports from tools.web_search.py.

### Task 2: Separate direct page reading from discovery

**Files:**
- Modify: tools/web_research.py
- Modify: tools/web_search.py
- Modify: app.py

**Interfaces:**
- open_public_page(url: str, max_chars: int = 12000) -> SearchSource.
- search_and_read(query: str, max_sites: int = 3, max_chars_per_site: int = 2500) -> SearchOutcome.

- [ ] Implement HTTP(S)-only retrieval, reject embedded credentials and local/private/reserved IP destinations, and revalidate every redirect before following it; return a blocked-destination status when rejected.
- [ ] Capture title/canonical URL, extraction status, and bounded page content.
- [ ] Implement web_open dispatch through LocalToolExecutor without changing the Chrome tab.
- [ ] Make web_search discovery-only and return ranked candidates with available snippets/status instead of silently reading full pages.
- [ ] Review user-facing and model-facing summaries so source URLs remain directly visible.

### Task 3: Normalize deep and technical research

**Files:**
- Modify: tools/web_research.py
- Modify: tools/web_search.py
- Modify: app.py

**Interfaces:**
- deep_search(query: str, max_sites: int = 7, max_chars_per_site: int = 3000) -> SearchOutcome.
- code_search(query: str, max_sites: int = 5, max_chars_per_site: int = 3000) -> SearchOutcome.

- [ ] Rebuild deep_search on discover_sources plus open_public_page; retain per-source status and partial results.
- [ ] Rebuild code_search to prioritize official docs/repositories, use PyPI fast path for single package names, and preserve source attribution.
- [ ] Ensure all result ordering follows discovery rank, even when page extraction runs concurrently.
- [ ] Return an explicit failure when no source content could be extracted, while retaining discovered candidate URLs.

### Task 4: Expose the research workflow to compatible providers

**Files:**
- Modify: providers/compatible_agent.py
- Modify: app.py
- Modify: README.md

**Interfaces:**
- Tool schemas: web_search(query), web_open(url, max_chars), deep_search(query), code_search(query).
- Results: JSON-compatible SearchOutcome mappings, serialized by the existing compatible-agent normalizer.

- [ ] Add web_open schema and dispatch; revise descriptions and system guidance for discovery → open selected sources → synthesize with citations.
- [ ] Clarify when to use web_search, web_open, deep_search, and code_search; prevent search results from being presented as extracted page contents.
- [ ] Ensure partial/error statuses are visible to the model and UI without relying solely on string prefixes.
- [ ] Document research tool behavior, result states, source citation requirements, and limits.
- [ ] Review the complete path from provider schema through LocalToolExecutor and result serialization.

---
