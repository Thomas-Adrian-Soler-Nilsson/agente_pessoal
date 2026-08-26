import concurrent.futures

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


def search_urls(query, max_results=5):
    """Pesquisa usando a lib ddgs (mais resistente a bloqueio que scraping cru)."""
    query = (query or "").strip()
    if not query:
        return []

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []

    return [
        {"title": item.get("title", ""), "url": item.get("href", "")}
        for item in results
        if item.get("href")
    ]


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

    contents = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_sites) as executor:
        futures = {
            executor.submit(_fetch_one, item["url"], max_chars_per_site): item
            for item in picked
        }

        for future in concurrent.futures.as_completed(futures, timeout=15):
            item = futures[future]
            try:
                text = future.result()
            except Exception:
                text = None

            if text:
                contents[item["url"]] = (item["title"], text)

    if not contents:
        return (
            f"Encontrei resultados para '{query}', mas não consegui "
            "extrair o conteúdo das páginas. Tentando busca simples..."
        )

    parts = [f"Pesquisa: {query}\n"]

    for url, (title, text) in contents.items():
        parts.append(f"Fonte: {title} ({url})\n{text}\n")

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

    contents = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_sites) as executor:
        futures = {
            executor.submit(_fetch_one, item["url"], max_chars_per_site): item
            for item in picked
        }

        for future in concurrent.futures.as_completed(futures, timeout=25):
            item = futures[future]
            try:
                text = future.result()
            except Exception:
                text = None

            if text:
                contents[item["url"]] = (item["title"], text)

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
    contents = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_sites) as executor:
        futures = {
            executor.submit(_fetch_one, item["url"], max_chars_per_site): item
            for item in picked
        }

        for future in concurrent.futures.as_completed(futures, timeout=20):
            item = futures[future]
            try:
                text = future.result()
            except Exception:
                text = None

            if text:
                contents[item["url"]] = (item["title"], text)

    if not contents:
        return f"Encontrei páginas para '{query}', mas não consegui extrair conteúdo."

    parts = [f"Pesquisa técnica: {query}\n"]
    for url, (title, text) in contents.items():
        parts.append(f"Fonte: {title} ({url})\n{text}\n")

    return "\n".join(parts)