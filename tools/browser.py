import os
from pathlib import Path
from urllib.parse import urlsplit


class BrowserTools:
    """Controla uma sessão Chromium persistente através do Playwright."""

    def __init__(self, page=None, user_data_dir=None, headless=None):
        self.page = page
        self._playwright = None
        self._context = None
        self.user_data_dir = Path(
            user_data_dir
            or os.getenv(
                "BROWSER_USER_DATA_DIR",
                str(Path.home() / ".agente_pessoal" / "browser"),
            )
        )
        self.headless = (
            headless
            if headless is not None
            else os.getenv("BROWSER_HEADLESS", "false").strip().lower()
            in {"1", "true", "sim", "yes"}
        )

    def _get_page(self):
        if self.page is not None:
            return self.page

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise RuntimeError(
                "Playwright não está instalado. Execute: pip install playwright"
            ) from error

        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            str(self.user_data_dir),
            headless=self.headless,
        )
        self.page = (
            self._context.pages[0]
            if self._context.pages
            else self._context.new_page()
        )
        return self.page

    @staticmethod
    def _validate_url(url):
        value = (url or "").strip()
        if not value:
            return None, "Informe qual URL devo abrir."

        try:
            parsed = urlsplit(value)
        except ValueError:
            return None, "Informe uma URL válida."

        scheme = parsed.scheme.lower()
        if scheme and scheme not in {"http", "https"}:
            return None, "A URL deve usar http:// ou https://."
        if not scheme:
            value = "https://" + value

        try:
            parsed = urlsplit(value)
        except ValueError:
            return None, "Informe uma URL válida."

        if not parsed.hostname or any(char.isspace() for char in value):
            return None, "Informe uma URL válida."
        return value, None

    def navigate(self, url):
        value, error = self._validate_url(url)
        if error:
            return error

        try:
            page = self._get_page()
            page.goto(value, wait_until="domcontentloaded")
            return f"Página aberta: {page.title()} ({page.url})"
        except Exception as error:
            return f"Não consegui abrir a página: {error}"

    def read(self, max_chars=None):
        try:
            page = self._get_page()
            text = page.locator("body").inner_text()
            limit = int(
                max_chars
                or os.getenv("BROWSER_MAX_TEXT_CHARS", "12000")
            )
            if len(text) > limit:
                return text[:limit] + "\n\n[CONTEÚDO TRUNCADO]"
            return text
        except Exception as error:
            return f"Não consegui ler a página: {error}"

    def click(self, selector):
        selector = (selector or "").strip()
        if not selector:
            return "Informe o seletor do elemento que devo clicar."

        try:
            self._get_page().locator(selector).click()
            return f"Cliquei no elemento '{selector}'."
        except Exception as error:
            return f"Não consegui clicar em '{selector}': {error}"

    def fill(self, selector, value):
        selector = (selector or "").strip()
        if not selector:
            return "Informe o seletor do campo que devo preencher."

        try:
            self._get_page().locator(selector).fill(value or "")
            return f"Preenchi o elemento '{selector}'."
        except Exception as error:
            return f"Não consegui preencher '{selector}': {error}"

    def close(self):
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()
        self.page = None
        self._context = None
        self._playwright = None
