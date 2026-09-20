import unittest
from unittest.mock import patch

from tools import web_search


class WebSearchTests(unittest.TestCase):
    @patch.object(web_search, "search_urls", return_value=[{"title": "Example", "url": "https://example.com"}])
    @patch.object(web_search, "_fetch_one", return_value="conteudo exemplo")
    def test_search_and_read_returns_text(self, fetch_one, search_urls):
        result = web_search.search_and_read("teste")
        self.assertIn("Pesquisa:", result)
        self.assertIn("example.com", result)
        self.assertIn("conteudo exemplo", result)

    @patch.object(web_search, "search_urls", return_value=[{"title": "Example", "url": "https://example.com"}])
    @patch.object(web_search, "_fetch_one", return_value="conteudo profundo")
    def test_deep_search_returns_text(self, fetch_one, search_urls):
        result = web_search.deep_search("teste")
        self.assertIn("Pesquisa profunda:", result)
        self.assertIn("conteudo profundo", result)


if __name__ == "__main__":
    unittest.main()
