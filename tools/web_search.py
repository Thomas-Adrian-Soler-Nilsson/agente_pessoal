import concurrent.futures
import re
from urllib.parse import urlsplit

import requests as _requests_lib

import requests
import trafilatura
from ddgs import DDGS


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _probe_url(item):
    """Confirma que o resultado existe e segue redirects antes de entregá-lo."""
    url = item.get("url", "")
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=(4, 8),
            allow_redirects=True,
            stream=True,
        )
        status = response.status_code
        final_url = response.url
        response.close()
        if status < 200 or status >= 400:
            return None
        parsed = urlsplit(final_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        item = dict(item)
        item["url"] = final_url
        item["status"] = status
        return item
    except Exception:
        return None


def _rank_url(item, query):
    text = f"{item.get('title', '')} {item.get('url', '')}".lower()
    terms = [term for term in re.findall(r"[\w.-]+", query.lower()) if len(term) > 2]
    score = sum(3 if term in item.get("title", "").lower() else 1 for term in terms if term in text)
    url = item.get("url", "").lower()
    if any(marker in url for marker in ("/tags/", "/search", "/category", "?q=")):
        score -= 3
    if any(term in query.lower() for term in ("download", "baixar", "modelo", "asset")):
        if any(marker in text for marker in ("download", ".glb", ".gltf", ".zip", "downloadable")):
            score += 4
    return score


def search_urls(query, max_results=5):
    """Busca, valida, segue redirects, remove duplicatas e ranqueia URLs."""
    query = (query or "").strip()
    if not query:
        return []

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []

    candidates = [
        {"title": item.get("title", ""), "url": item.get("href", "")}
        for item in results
        if item.get("href")
    ]
    unique = []
    seen = set()
    for item in candidates:
        key = item["url"].split("#", 1)[0].rstrip("/").lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(unique) or 1)) as pool:
        checked = list(pool.map(_probe_url, unique[: max_results * 3]))
    valid = [item for item in checked if item]
    valid.sort(key=lambda item: _rank_url(item, query), reverse=True)
    return valid[:max_results]


def _fetch_one(url, max_chars):
    """Baixa e extrai o texto principal de uma única página."""
    try:
        downloaded = trafilatura.fetch_url(url)

        if not downloaded:
            response = requests.get(url, headers=HEADERS, timeout=8)
            downloaded = response.text

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
        )

        if not text:
            return None

        if len(text) > max_chars:
            text = text[:max_chars] + "\n[TRUNCADO]"

        return text
    except Exception:
        return None


def _fetch_many(items, max_chars, timeout):
    """Fetch pages with a hard deadline and keep partial results."""
    if not items:
        return {}
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(items)))
    futures = {
        executor.submit(_fetch_one, item["url"], max_chars): item
        for item in items
    }
    contents = {}
    try:
        done, _ = concurrent.futures.wait(futures, timeout=timeout)
        for future in done:
            item = futures[future]
            try:
                text = future.result()
            except Exception:
                text = None
            if text:
                contents[item["url"]] = (item["title"], text)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return contents


def search_and_read(query, max_sites=3, max_chars_per_site=2500):
    """
    Pesquisa e lê múltiplos sites em paralelo.

    Controla o gasto de tokens: no máximo max_sites páginas,
    cada uma truncada em max_chars_per_site caracteres.
    """
    urls = search_urls(query, max_results=max_sites + 2)

    if not urls:
        return f"Não encontrei resultados para '{query}'."

    picked = urls[:max_sites]

    contents = _fetch_many(picked, max_chars_per_site, timeout=15)

    if not contents:
        return (
            f"Encontrei resultados para '{query}', mas não consegui "
            "extrair o conteúdo das páginas. Tentando busca simples..."
        )

    parts = [f"Pesquisa: {query}\n"]

    for url, (title, text) in contents.items():
        parts.append(f"Fonte: {title} ({url})\n{text}\n")

    return "\n".join(parts)

def deep_search(query, max_sites=7, max_chars_per_site=3000):
    """
    Pesquisa profunda: mais fontes, mais conteúdo por fonte.

    Usa mais tokens que search_and_read, então deve ser reservada
    para pedidos que realmente pedem uma pesquisa completa/detalhada.
    """
    urls = search_urls(query, max_results=max_sites + 3)

    if not urls:
        return f"Não encontrei resultados para '{query}'."

    picked = urls[:max_sites]

    contents = _fetch_many(picked, max_chars_per_site, timeout=25)

    if not contents:
        return (
            f"Encontrei resultados para '{query}', mas não consegui "
            "extrair conteúdo de nenhuma página."
        )

    parts = [
        f"Pesquisa profunda: {query}",
        f"({len(contents)} fontes analisadas)\n",
    ]

    for i, (url, (title, text)) in enumerate(contents.items(), start=1):
        parts.append(f"--- Fonte {i}: {title} ({url}) ---\n{text}\n")

    return "\n".join(parts)


import requests as _requests_lib


def pypi_lookup(package_name):
    """Consulta direta e rápida na API oficial do PyPI para um pacote."""
    package_name = (package_name or "").strip()
    if not package_name:
        return None

    try:
        response = _requests_lib.get(
            f"https://pypi.org/pypi/{package_name}/json", timeout=6
        )
        if response.status_code != 200:
            return None

        data = response.json()
        info = data.get("info", {})

        summary = info.get("summary", "")
        description = (info.get("description") or "")[:2000]
        version = info.get("version", "")
        home_page = info.get("home_page") or info.get("project_url", "")
        requires_python = info.get("requires_python", "")

        return (
            f"Pacote: {package_name} (PyPI)\n"
            f"Versão atual: {version}\n"
            f"Resumo: {summary}\n"
            f"Requer Python: {requires_python or 'não especificado'}\n"
            f"Página: {home_page}\n\n"
            f"Descrição:\n{description}"
        )
    except Exception:
        return None


def code_search(query, max_sites=5, max_chars_per_site=3000):
    """
    Pesquisa voltada para programação: prioriza documentação oficial,
    Stack Overflow, GitHub e ReadTheDocs.

    Se a query parecer o nome de um único pacote Python, tenta o PyPI
    primeiro (mais rápido e estruturado que busca na web).
    """
    query = (query or "").strip()
    if not query:
        return "Informe o que devo pesquisar."

    # Atalho: se for uma única palavra, pode ser nome de pacote.
    if " " not in query:
        pypi_result = pypi_lookup(query)
        if pypi_result:
            return pypi_result

    biased_query = (
        f"{query} "
        "(site:stackoverflow.com OR site:github.com OR "
        "site:docs.python.org OR site:readthedocs.io OR "
        "site:developer.mozilla.org)"
    )

    urls = search_urls(biased_query, max_results=max_sites + 3)

    # Se a busca com viés de sites não trouxer nada, tenta sem viés.
    if not urls:
        urls = search_urls(query, max_results=max_sites + 3)

    if not urls:
        return f"Não encontrei resultados de código/documentação para '{query}'."

    picked = urls[:max_sites]
    contents = _fetch_many(picked, max_chars_per_site, timeout=20)

    if not contents:
        return f"Encontrei páginas para '{query}', mas não consegui extrair conteúdo."

    parts = [f"Pesquisa técnica: {query}\n"]
    for url, (title, text) in contents.items():
        parts.append(f"Fonte: {title} ({url})\n{text}\n")

    return "\n".join(parts)
