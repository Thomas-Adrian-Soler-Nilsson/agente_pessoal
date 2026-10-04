"""Structured, source-attributed public web research operations."""
from __future__ import annotations

import concurrent.futures
import ipaddress
import socket
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import requests

import re
import math
from bs4 import BeautifulSoup
import trafilatura
from ddgs import DDGS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
REDIRECT_CODES = {301, 302, 303, 307, 308}
MAX_PAGE_BYTES = 3_000_000


def _public_destination(url: str) -> tuple[str | None, str | None]:
    """Return normalized public HTTP(S) URL or a stable block reason."""
    try:
        parsed = urlsplit((url or "").strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None, "unsupported_url"
        if parsed.username is not None or parsed.password is not None:
            return None, "embedded_credentials"
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return None, "private_destination"
        try:
            addresses = {ipaddress.ip_address(host)}
        except ValueError:
            try:
                addresses = {
                    ipaddress.ip_address(item[4][0].split("%", 1)[0])
                    for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
                }
            except (OSError, ValueError):
                return None, "dns_failure"
        if not addresses or any(not address.is_global for address in addresses):
            return None, "private_destination"
        netloc = parsed.netloc
        normalized = urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))
        return normalized, None
    except (TypeError, ValueError):
        return None, "unsupported_url"


def _fetch_public(url: str, max_redirects: int = 5) -> tuple[requests.Response | None, str | None]:
    current, error = _public_destination(url)
    if error:
        return None, error
    for _ in range(max_redirects + 1):
        try:
            response = requests.get(current, headers=HEADERS, timeout=(5, 12), allow_redirects=False, stream=True)
        except requests.Timeout:
            return None, "timeout"
        except requests.RequestException as exc:
            return None, "network_error:" + type(exc).__name__
        if response.status_code in REDIRECT_CODES:
            location = response.headers.get("Location")
            response.close()
            if not location:
                return None, "redirect_without_location"
            target, error = _public_destination(urljoin(current, location))
            if error:
                return None, error
            current = target
            continue
        response.url = current
        return response, None
    return None, "too_many_redirects"


def _source(title="", url="", snippet="", status="candidate", **extra):
    parsed = urlsplit(url) if url else None
    item = {
        "title": title or (url or "Sem título"),
        "url": url,
        "domain": parsed.hostname if parsed else "",
        "snippet": snippet,
        "status": status,
    }
    item.update(extra)
    return item


def _canonical(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "/", parsed.query, ""))



def _score_passage(passage: str, terms: list[str], avgdl: float = 50.0, k1: float = 1.5, b: float = 0.75) -> float:
    if not terms or not passage:
        return 1.0
    passage_lower = passage.lower()
    words = re.findall(r'\w+', passage_lower)
    if not words:
        return 0.0
    passage_len = len(words)
    import collections
    term_counts = collections.Counter(words)
    score = 0.0
    for term in terms:
        tf = term_counts.get(term, 0)
        if tf > 0:
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (passage_len / max(1.0, avgdl)))
            score += (numerator / denominator) * len(term)
    return score

def _extract_relevant_passages(text: str, query: str, max_chars: int) -> str:
    if not text:
        return ""
    text = re.sub(r'\n{3,}', '\n\n', text)
    blocks = [b.strip() for b in text.split('\n\n') if len(b.strip()) > 20]
    if not blocks:
        blocks = [b.strip() for b in text.split('\n') if len(b.strip()) > 20]
    if not blocks:
        return text[:max_chars]
        
    if not query:
        result = []
        current_len = 0
        for b in blocks:
            if current_len + len(b) > max_chars and result:
                break
            result.append(b)
            current_len += len(b) + 2
        return "\n\n".join(result)

    terms = [t for t in re.split(r'\W+', query.lower()) if len(t) > 2]
    
    words_per_block = [len(re.findall(r'\w+', b.lower())) for b in blocks]
    avgdl = sum(words_per_block) / len(words_per_block) if words_per_block else 1.0

    scored = []
    for i, b in enumerate(blocks):
        scored.append((_score_passage(b, terms, avgdl), i, b))
        
    scored.sort(key=lambda x: x[0], reverse=True)
    
    selected = []
    current_len = 0
    for score, i, b in scored:
        if current_len + len(b) > max_chars and selected:
            continue
        selected.append((i, b))
        current_len += len(b) + 2
        if current_len >= max_chars:
            break
            
    selected.sort(key=lambda x: x[0])
    return "\n\n[... ...]\n\n".join(b for i, b in selected)

def discover_sources(query: str, max_results: int = 5) -> dict:
    query = (query or "").strip()
    if not query:
        return {"status": "failure", "query": query, "backend": "ddgs", "sources": [], "errors": ["empty_query"]}
    limit = max(1, min(int(max_results or 5), 10))
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=limit))
    except Exception as exc:
        return {"status": "failure", "query": query, "backend": "ddgs", "sources": [], "errors": ["search_backend:" + type(exc).__name__]}
    sources = []
    seen = set()
    rejected = 0
    for item in raw:
        url = (item.get("href") or item.get("url") or "").strip()
        if not url:
            continue
        normalized, error = _public_destination(url)
        if error:
            rejected += 1
            sources.append(_source(item.get("title", ""), url, item.get("body", ""), "blocked", error_code=error))
            continue
        key = _canonical(normalized)
        if key in seen:
            continue
        seen.add(key)
        sources.append(_source(item.get("title", ""), normalized, item.get("body", ""), "candidate"))
    visible = sources[:limit]
    if not raw:
        status = "empty"
    elif rejected or len(visible) < min(limit, len(raw)):
        status = "partial" if any(item["status"] == "candidate" for item in visible) else "failure"
    else:
        status = "success"
    return {"status": status, "query": query, "backend": "ddgs", "sources": visible, "errors": ["blocked_destinations"] if rejected else []}


def open_public_page(url: str, max_chars: int = 12000, focus_query: str = "") -> dict:
    normalized, error = _public_destination(url)
    if error:
        return _source(url=url, status="blocked", error_code=error, content="")
    response, error = _fetch_public(normalized)
    if error:
        return _source(url=normalized, status="failure", error_code=error, content="")
    try:
        if response.status_code < 200 or response.status_code >= 400:
            return _source(url=response.url, status="failure", error_code="http_" + str(response.status_code), content="")
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type and not any(kind in content_type for kind in ("text/html", "application/xhtml+xml", "text/plain")):
            return _source(url=response.url, status="failure", error_code="unsupported_content_type", content="")
        chunks = []
        size = 0
        for chunk in response.iter_content(65536):
            if not chunk:
                continue
            remaining = MAX_PAGE_BYTES - size
            chunks.append(chunk[:remaining])
            size += min(len(chunk), remaining)
            if size >= MAX_PAGE_BYTES:
                break
        truncated_by_limit = size >= MAX_PAGE_BYTES
        raw = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        title = ""
        extracted = trafilatura.extract(raw, include_comments=False, include_tables=True, output_format="txt")
        if not extracted or len(extracted.strip()) < 50:
            # Fallback to BeautifulSoup
            soup = BeautifulSoup(raw, "html.parser")
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            extracted = soup.get_text(separator='\n\n', strip=True)
            
        def _is_js_locked(text: str) -> bool:
            t = text.lower()
            return any(p in t for p in [
                "enable javascript", "javascript is disabled", "turn on javascript",
                "requires javascript", "please wait while your request is being verified",
                "just a moment...", "checking your browser", "security check"
            ])

        if not extracted or len(extracted.strip()) < 20 or _is_js_locked(extracted):
            # Fallback dinâmico via BrowserTools. A aba anônima precisa ser fechada
            # mesmo quando a extração falha: antes, cada tentativa deixava uma aba
            # aberta no perfil do usuário.
            browser = None
            tab_id = None
            try:
                from tools.browser import BrowserTools
                browser = BrowserTools()
                tab_res = browser.open_tab(response.url, incognito=True)
                if tab_res.get("status") == "success":
                    # A resposta de open_tab traz "tab" e um "data" com valor None.
                    # Usar .get("data", {}) devolvia None e lançava AttributeError,
                    # engolido pelo except: o fallback nunca funcionava.
                    tab_id = (tab_res.get("data") or {}).get("tab_id") or (tab_res.get("tab") or {}).get("id")
                    if tab_id:
                        browser.wait(tab_id, timeout=8)
                        inspect_res = browser.inspect(tab_id, max_chars=max_chars)
                        if inspect_res.get("status") == "success":
                            extracted = (inspect_res.get("data") or {}).get("text", "")
            except Exception:
                pass
            finally:
                if browser is not None:
                    if tab_id:
                        try:
                            browser.close_tab(tab_id)
                        except Exception:
                            pass
                    try:
                        browser.close()
                    except Exception:
                        pass

        if not extracted or len(extracted.strip()) < 20:
            status = "extraction_failure"
            content = ""
        else:
            status = "success"
            # Limit total char budget for performance
            max_limit = max(500, min(int(max_chars or 12000), 24000))
            best_passages = _extract_relevant_passages(extracted, focus_query, max_limit)
            content = best_passages
        metadata = trafilatura.extract_metadata(raw)
        if metadata and metadata.title:
            title = metadata.title
            
        final_title = title or response.url
        if status == "success":
            # Cleanly format markdown block
            md_content = f"# {final_title}\n**URL:** `{response.url}`\n\n" + content
            content = md_content
            
        return _source(final_title, response.url, status=status, content=content, http_status=response.status_code)
    except Exception as exc:
        return _source(url=response.url, status="failure", error_code="extraction_error:" + type(exc).__name__, content="")
    finally:
        response.close()


def _read_sources(query: str, max_sites: int, max_chars_per_site: int, search_query: str | None = None, preferred_domains: tuple[str, ...] = ()) -> dict:
    discovered = discover_sources(search_query or query, max_results=max_sites + 3)
    candidates = [item for item in discovered["sources"] if item["status"] == "candidate"]
    if preferred_domains:
        candidates.sort(key=lambda item: next((index for index, domain in enumerate(preferred_domains) if (item.get("domain") or "").lower() == domain or (item.get("domain") or "").lower().endswith("." + domain)), len(preferred_domains)))
    candidates = candidates[:max_sites]
    if not candidates:
        return {"status": discovered["status"], "query": query, "backend": discovered["backend"], "sources": discovered["sources"], "errors": discovered["errors"]}
    indexed = {}
    workers = min(5, len(candidates))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(open_public_page, item["url"], max_chars_per_site, focus_query=query): index for index, item in enumerate(candidates)}
        for future in concurrent.futures.as_completed(future_map):
            index = future_map[future]
            try:
                page = future.result()
            except Exception as exc:
                page = _source(url=candidates[index]["url"], status="failure", error_code="fetch_error:" + type(exc).__name__, content="")
            page["snippet"] = candidates[index].get("snippet", "")
            if not page.get("title") or page["title"] == page.get("url"):
                page["title"] = candidates[index].get("title") or page.get("url")
            indexed[index] = page
    pages = [indexed[index] for index in sorted(indexed)]
    success_count = sum(page["status"] == "success" for page in pages)
    status = "success" if success_count == len(pages) else "partial" if success_count else "failure"
    rejected = [item for item in discovered["sources"] if item["status"] == "blocked"]
    if rejected and status == "success":
        status = "partial"
    return {"status": status, "query": query, "backend": discovered["backend"], "sources": pages, "rejected_sources": rejected, "errors": discovered["errors"]}


def deep_search(query: str, max_sites: int = 7, max_chars_per_site: int = 3000) -> dict:
    query = (query or "").strip()
    if not query:
        return {"status": "failure", "query": query, "backend": "ddgs", "sources": [], "errors": ["empty_query"]}
    return _read_sources(query, max(1, min(int(max_sites or 7), 10)), max_chars_per_site)


def code_search(query: str, max_sites: int = 5, max_chars_per_site: int = 3000) -> dict:
    query = (query or "").strip()
    if not query:
        return {"status": "failure", "query": query, "backend": "ddgs", "sources": [], "errors": ["empty_query"]}
    if " " not in query:
        try:
            response = requests.get("https://pypi.org/pypi/" + quote(query) + "/json", headers=HEADERS, timeout=(4, 8))
            if response.status_code == 200:
                info = response.json().get("info", {})
                content = "\n".join(part for part in (info.get("summary", ""), info.get("description", "")[:2000]) if part)
                return {"status": "success", "query": query, "backend": "pypi", "sources": [_source(info.get("name", query), "https://pypi.org/project/" + query + "/", status="success", content=content, version=info.get("version", ""), requires_python=info.get("requires_python", ""))], "errors": []}
        except (requests.RequestException, ValueError):
            pass
    biased = query + " (site:stackoverflow.com OR site:github.com OR site:docs.python.org OR site:readthedocs.io OR site:developer.mozilla.org)"
    result = _read_sources(query, max(1, min(int(max_sites or 5), 8)), max_chars_per_site, search_query=biased, preferred_domains=("docs.python.org", "developer.mozilla.org", "github.com", "pypi.org", "readthedocs.io", "stackoverflow.com"))
    if not result["sources"] or result["status"] == "failure":
        return _read_sources(query, max(1, min(int(max_sites or 5), 8)), max_chars_per_site)
    result["backend"] = "ddgs:technical"
    return result
