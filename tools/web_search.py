"""
Legacy module for web search.
This module now delegates entirely to tools.web_research.
"""

from tools.web_research import discover_sources, deep_search as _deep_search, code_search as _code_search

def search_urls(query, max_results=5):
    """Busca, valida, segue redirects, remove duplicatas e ranqueia URLs."""
    result = discover_sources(query, max_results=max_results)
    return result.get("sources", [])

def search_and_read(query, max_sites=3, max_chars_per_site=2500):
    """
    Pesquisa e lê múltiplos sites em paralelo delegando ao web_research.
    """
    return _deep_search(query, max_sites=max_sites, max_chars_per_site=max_chars_per_site)

def deep_search(query, max_sites=7, max_chars_per_site=3000):
    """
    Pesquisa profunda.
    """
    return _deep_search(query, max_sites=max_sites, max_chars_per_site=max_chars_per_site)

def code_search(query, max_sites=5, max_chars_per_site=3000):
    """
    Pesquisa voltada para programação.
    """
    return _code_search(query, max_sites=max_sites, max_chars_per_site=max_chars_per_site)
