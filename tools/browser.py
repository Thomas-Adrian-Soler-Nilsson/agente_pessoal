import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote_plus, urlsplit


class BrowserTools:
    """Controla uma sessão Chromium persistente através do Playwright.

    Toda a API síncrona do Playwright roda dentro de uma única thread
    dedicada. Isso evita que o event loop interno criado pelo Playwright
    interfira no event loop usado por outras partes do programa (como o
    TTS, que chama asyncio.run() repetidamente na thread principal).
    """

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

        # Thread dedicada onde todo o Playwright (sync API) roda.
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="browser-tools"
        )

    # -----------------------------------------------------------------
    # INFRAESTRUTURA DE THREAD
    # -----------------------------------------------------------------

    def _run(self, func, *args, **kwargs):
        """Executa func na thread dedicada e espera o resultado."""
        future = self._executor.submit(func, *args, **kwargs)
        return future.result()

    def _get_page(self):
        """Deve ser chamado apenas de dentro da thread dedicada."""
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

    # -----------------------------------------------------------------
    # OPERAÇÕES INTERNAS (rodam dentro da thread dedicada)
    # -----------------------------------------------------------------

    def _read_text(self, max_chars=None):
        page = self._get_page()
        text = page.locator("body").inner_text()
        limit = int(max_chars or os.getenv("BROWSER_MAX_TEXT_CHARS", "12000"))
        if len(text) > limit:
            return text[:limit] + "\n\n[CONTEÚDO TRUNCADO]"
        return text

    def _navigate_impl(self, url):
        value, error = self._validate_url(url)
        if error:
            return error

        try:
            page = self._get_page()
            page.goto(value, wait_until="domcontentloaded")
            title = page.title()
            content = self._read_text()
            return (
                f"Página aberta: {title} ({page.url})\n\n"
                f"Conteúdo da página:\n{content}"
            )
        except Exception as error:
            return f"Não consegui abrir a página: {error}"

    def _read_impl(self, max_chars=None):
        try:
            return self._read_text(max_chars)
        except Exception as error:
            return f"Não consegui ler a página: {error}"

    def _click_impl(self, selector):
        selector = (selector or "").strip()
        if not selector:
            return "Informe o seletor do elemento que devo clicar."

        try:
            self._get_page().locator(selector).click()
            return f"Cliquei no elemento '{selector}'."
        except Exception as error:
            return f"Não consegui clicar em '{selector}': {error}"

    def _fill_impl(self, selector, value):
        selector = (selector or "").strip()
        if not selector:
            return "Informe o seletor do campo que devo preencher."

        try:
            self._get_page().locator(selector).fill(value or "")
            return f"Preenchi o elemento '{selector}'."
        except Exception as error:
            return f"Não consegui preencher '{selector}': {error}"

    def _search_impl(self, query, open_first_result=True):
        query = (query or "").strip()
        if not query:
            return "Informe o que devo pesquisar."

        try:
            page = self._get_page()
            search_url = (
                "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
            )
            page.goto(search_url, wait_until="domcontentloaded")

            # A versão HTML do DuckDuckGo usa links com essa classe.
            links = page.locator("a.result__a")
            count = links.count()

            results = []
            for i in range(min(count, 5)):
                try:
                    href = links.nth(i).get_attribute("href")
                    label = links.nth(i).inner_text()
                    if href:
                        results.append((label.strip(), href.strip()))
                except Exception:
                    continue

            if not results:
                return (
                    f"Não encontrei resultados para '{query}'. "
                    "Tente reformular a busca."
                )

            if not open_first_result:
                listing = "\n".join(
                    f"- {label}: {href}" for label, href in results
                )
                return f"Resultados para '{query}':\n{listing}"

            first_label, first_url = results[0]
            page.goto(first_url, wait_until="domcontentloaded")
            title = page.title()
            content = self._read_text()

            others = "\n".join(
                f"- {label}: {href}" for label, href in results[1:]
            )

            return (
                f"Pesquisei '{query}' e abri o primeiro resultado: "
                f"{title} ({page.url})\n\n"
                f"Conteúdo da página (use isto como fonte):\n{content}"
                + (
                    f"\n\nOutros resultados encontrados:\n{others}"
                    if others
                    else ""
                )
            )
        except Exception as error:
            return f"Não consegui pesquisar '{query}': {error}"

    def _close_impl(self):
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()
        self.page = None
        self._context = None
        self._playwright = None

    # -----------------------------------------------------------------
    # API PÚBLICA (chamada de qualquer thread, despacha para a thread
    # dedicada e espera o resultado)
    # -----------------------------------------------------------------

    def navigate(self, url):
        return self._run(self._navigate_impl, url)

    def read(self, max_chars=None):
        return self._run(self._read_impl, max_chars)

    def click(self, selector):
        return self._run(self._click_impl, selector)

    def fill(self, selector, value):
        return self._run(self._fill_impl, selector, value)

    def search(self, query, open_first_result=True):
        return self._run(self._search_impl, query, open_first_result)

    def close(self):
        try:
            self._run(self._close_impl)
        finally:
            self._executor.shutdown(wait=False)