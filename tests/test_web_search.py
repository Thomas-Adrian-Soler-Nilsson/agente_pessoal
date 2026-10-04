import unittest
from unittest.mock import patch

from tools import web_search


class WebSearchTests(unittest.TestCase):
    @patch.object(web_search, "discover_sources", return_value={"status": "success", "sources": [{"title": "Example", "url": "https://example.com"}]})
    def test_search_urls(self, discover_mock):
        result = web_search.search_urls("teste")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url"], "https://example.com")

    @patch.object(web_search, "_deep_search", return_value={"status": "success", "sources": [{"title": "Example", "url": "https://example.com", "content": "conteudo exemplo"}]})
    def test_deep_search_returns_dict(self, read_sources_mock):
        result = web_search.deep_search("teste")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["sources"][0]["content"], "conteudo exemplo")


if __name__ == "__main__":
    unittest.main()
