import asyncio
import base64
import os
import queue
import threading
from pathlib import Path
from urllib.parse import urljoin, urlsplit


class BrowserTools:
    """Sessão Chromium persistente com API assíncrona isolada do agente."""

    def __init__(self, page=None, user_data_dir=None, headless=None):
        self.page = page
        self._playwright = None
        self._context = None
        self.user_data_dir = Path(user_data_dir or os.getenv("BROWSER_USER_DATA_DIR", str(Path.home() / ".agente_pessoal" / "browser")))
        self.headless = headless if headless is not None else os.getenv("BROWSER_HEADLESS", "false").lower() in {"1", "true", "sim", "yes"}
        self._jobs = queue.Queue()
        self._thread = None
        self._ready = threading.Event()
        self._startup_error = None
        self._closed = False

    @staticmethod
    def _validate_url(url):
        value = (url or "").strip()
        if not value:
            return None, "Informe qual URL devo abrir."
        try:
            parsed = urlsplit(value)
        except ValueError:
            return None, "Informe uma URL válida."
        if not parsed.scheme:
            value = "https://" + value
            parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"}:
            return None, "A URL deve usar http:// ou https://."
        if not parsed.hostname or any(char.isspace() for char in value):
            return None, "Informe uma URL válida."
        return value, None

    def _ensure_worker(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = None
        self._closed = False
        self._startup_error = None
        self._ready.clear()
        self._thread = threading.Thread(target=self._worker_main, name="agent-browser", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30):
            self._thread = None
            raise RuntimeError("o navegador não confirmou a inicialização em até 30s")
        if self._startup_error:
            error = self._startup_error
            self._thread = None
            raise RuntimeError(error)

    def _worker_main(self):
        try:
            asyncio.run(self._worker_loop())
        except Exception as error:
            self._startup_error = str(error)
            self._ready.set()

    async def _worker_loop(self):
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self._startup_error = "Playwright não está instalado. Execute: pip install playwright"
            self._ready.set()
            return
        try:
            self.user_data_dir.mkdir(parents=True, exist_ok=True)
            self._playwright = await async_playwright().start()
            try:
                self._context = await self._launch_context(self.user_data_dir)
            except Exception as first_error:
                # Perfil persistente pode estar travado por outra instância do
                # Chrome. Use um perfil isolado para esta sessão e continue.
                fallback = self.user_data_dir.parent / f"browser-session-{os.getpid()}-{threading.get_ident()}"
                try:
                    self.user_data_dir = fallback
                    self._context = await self._launch_context(fallback)
                except Exception:
                    raise first_error
            self.page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            self._ready.set()
            while not self._closed:
                job = await asyncio.to_thread(self._jobs.get)
                if job is None:
                    break
                operation, args, result_queue = job
                try:
                    if self.page is None or self.page.is_closed():
                        self.page = await self._context.new_page()
                    result_queue.put((True, await operation(self.page, *args)))
                except Exception as error:
                    result_queue.put((False, str(error)))
        finally:
            if self._context is not None:
                await self._context.close()
            if self._playwright is not None:
                await self._playwright.stop()

    async def _launch_context(self, profile):
        profile.mkdir(parents=True, exist_ok=True)
        return await self._playwright.chromium.launch_persistent_context(
            str(profile),
            headless=self.headless,
            accept_downloads=True,
            args=["--no-first-run", "--no-default-browser-check"],
        )

    def _call(self, operation, *args, timeout=45):
        try:
            self._ensure_worker()
        except Exception as error:
            return f"Não consegui iniciar o navegador: {error}"
        result_queue = queue.Queue(maxsize=1)
        self._jobs.put((operation, args, result_queue))
        try:
            success, result = result_queue.get(timeout=timeout)
        except queue.Empty:
            return f"O navegador excedeu o timeout de {timeout}s."
        return result if success else f"Falha no navegador: {result}"

    async def _navigate(self, page, url):
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        status = response.status if response else 200
        if status >= 400:
            return f"Navegação recusada: HTTP {status} em {page.url}. Não é uma página válida para continuar."
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        return f"Página aberta: HTTP {status} | {await page.title()} ({page.url})"

    async def _read(self, page, max_chars):
        text = await page.locator("body").inner_text(timeout=15000)
        limit = int(max_chars or os.getenv("BROWSER_MAX_TEXT_CHARS", "16000"))
        return text if len(text) <= limit else text[:limit] + "\n\n[CONTEÚDO TRUNCADO]"

    async def _snapshot(self, page, max_chars):
        title = await page.title()
        text = await page.locator("body").inner_text(timeout=15000)
        limit = int(max_chars or 12000)
        elements = await page.locator("a,button,input,select,textarea").evaluate_all(
            """els => els.slice(0, 80).map((el, i) => ({
                i,
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim().slice(0, 160),
                href: el.href || '',
                id: el.id || '',
                name: el.getAttribute('name') || '',
                type: el.getAttribute('type') || ''
            }))"""
        )
        lines = []
        for item in elements:
            selector = f"#{item['id']}" if item.get("id") else (
                f"[name='{item['name']}']" if item.get("name") else f"{item['tag']}:nth-of-type({item['i'] + 1})"
            )
            label = item.get("text") or item.get("href") or item.get("type") or item["tag"]
            lines.append(f"[{item['i']}] {item['tag']} {label} | seletor={selector}")
        return f"URL: {page.url}\nTítulo: {title}\nELEMENTOS:\n" + "\n".join(lines) + f"\n\nTEXTO:\n{text[:limit]}"

    async def _click(self, page, selector):
        await page.locator(selector).click(timeout=15000)
        return f"Cliquei no elemento '{selector}'."

    async def _fill(self, page, selector, value):
        await page.locator(selector).fill(value or "", timeout=15000)
        return f"Preenchi o elemento '{selector}'."

    async def _mouse_click(self, page, x, y, button):
        await page.mouse.click(float(x), float(y), button=button or "left")
        return f"Cliquei visualmente em ({x}, {y})."

    async def _mouse_move(self, page, x, y):
        await page.mouse.move(float(x), float(y))
        return f"Mouse movido para ({x}, {y})."

    async def _type(self, page, text, delay):
        await page.keyboard.type(text or "", delay=float(delay or 0))
        return "Texto digitado no navegador."

    async def _press(self, page, key):
        await page.keyboard.press(key)
        return f"Tecla pressionada: {key}."

    async def _screenshot(self, page, path):
        data = await page.screenshot(path=path or None, type="png")
        return {"type": "image", "data": base64.b64encode(data).decode("ascii"), "description": f"Screenshot do navegador em {page.url}"}

    async def _download(self, page, selector, path):
        async with page.expect_download(timeout=30000) as download_info:
            await page.locator(selector).click(timeout=15000)
        download = await download_info.value
        target = Path(path).expanduser() if path else Path.cwd() / download.suggested_filename
        target.parent.mkdir(parents=True, exist_ok=True)
        await download.save_as(str(target))
        return f"Download salvo em {target}"

    async def _search_site(self, page, query, max_pages):
        terms = [term.lower() for term in (query or "").split() if len(term) > 1]
        if not terms:
            return "Informe os termos que devo procurar no site."
        origin = page.url
        host = urlsplit(origin).netloc.lower()
        pending = [origin]
        visited = set()
        matches = []
        limit = max(1, min(int(max_pages or 5), 15))
        while pending and len(visited) < limit:
            target = pending.pop(0).split("#", 1)[0]
            if target in visited or urlsplit(target).netloc.lower() != host:
                continue
            visited.add(target)
            try:
                response = await page.goto(target, wait_until="domcontentloaded", timeout=20000)
                if response is None or response.status >= 400:
                    continue
                text = await page.locator("body").inner_text(timeout=10000)
                lowered = text.lower()
                if all(term in lowered for term in terms):
                    snippets = []
                    for term in terms:
                        index = lowered.find(term)
                        snippets.append(text[max(0, index - 180):index + 420].replace("\n", " "))
                    matches.append(f"URL: {page.url}\nTítulo: {await page.title()}\n" + "\n".join(snippets))
                links = await page.locator("a[href]").evaluate_all("els => els.map(a => a.href)")
                for link in links:
                    parsed = urlsplit(link)
                    if parsed.scheme in {"http", "https"} and parsed.netloc.lower() == host:
                        clean = urljoin(page.url, link).split("#", 1)[0]
                        if clean not in visited and clean not in pending:
                            pending.append(clean)
            except Exception:
                continue
        if origin and page.url != origin:
            try:
                await page.goto(origin, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass
        if not matches:
            return f"Nenhuma ocorrência de '{query}' encontrada nas {len(visited)} páginas válidas visitadas."
        return f"Pesquisa no site: {query}\nPáginas analisadas: {len(visited)}\n\n" + "\n\n---\n\n".join(matches)

    def navigate(self, url):
        value, error = self._validate_url(url)
        return error or self._call(self._navigate, value)

    def read(self, max_chars=None): return self._call(self._read, max_chars)
    def snapshot(self, max_chars=None): return self._call(self._snapshot, max_chars)
    def click(self, selector):
        selector = (selector or "").strip()
        return "Informe o seletor do elemento que devo clicar." if not selector else self._call(self._click, selector)
    def fill(self, selector, value):
        selector = (selector or "").strip()
        return "Informe o seletor do campo que devo preencher." if not selector else self._call(self._fill, selector, value or "")
    def mouse_click(self, x, y, button="left"): return self._call(self._mouse_click, x, y, button)
    def mouse_move(self, x, y): return self._call(self._mouse_move, x, y)
    def type_text(self, text, delay=0): return self._call(self._type, text or "", delay)
    def press(self, key): return self._call(self._press, key)
    def screenshot(self, path=""): return self._call(self._screenshot, path or None)
    def download(self, selector, path=""): return self._call(self._download, selector, path or "")
    def search_site(self, query, max_pages=5): return self._call(self._search_site, query or "", max_pages, timeout=120)

    def close(self):
        self._closed = True
        if self._thread is not None:
            self._jobs.put(None)
            self._thread.join(timeout=5)
        self._jobs = queue.Queue()
        self.page = None
        self._context = None
        self._playwright = None
        self._thread = None
