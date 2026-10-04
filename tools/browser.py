"""Chrome session browser tools backed by the local extension bridge."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from tools.browser_bridge import acquire_shared_browser_bridge, release_shared_browser_bridge
from tools.browser_protocol import result


def confirmar_acoes_arriscadas() -> bool:
    """Pedir [s/N] antes de enviar, publicar, comprar ou excluir?

    Desligado por padrao: o agente executa direto. Com
    AGENTE_CONFIRMAR_ACOES=1 a confirmacao volta a ser pedida.
    """
    return os.getenv("AGENTE_CONFIRMAR_ACOES", "").strip().lower() in {"1", "true", "sim", "yes", "on"}


class BrowserTools:
    def __init__(self, bridge=None):
        self.bridge = bridge if bridge is not None else acquire_shared_browser_bridge()
        self._owns_bridge = bridge is None

    def _call(self, operation, arguments=None, timeout=30):
        return self.bridge.execute(operation, arguments or {}, timeout=timeout)

    def list_tabs(self):
        return self._call("list_tabs")

    def inspect(self, tab_id, max_chars=12000):
        return self._call("inspect", {"tab_id": int(tab_id), "max_chars": int(max_chars or 12000)})

    def navigate(self, url, tab_id=None):
        return self._call("navigate", {"url": url, "tab_id": tab_id})

    def open_tab(self, url="", incognito=False):
        return self._call("open_tab", {"url": url, "incognito": incognito})

    def close_tab(self, tab_id):
        return self._call("close_tab", {"tab_id": int(tab_id)})

    def click(self, tab_id, element_ref, confirmation_token=""):
        return self._call("click", {"tab_id": int(tab_id), "element_ref": element_ref, "confirmation_token": confirmation_token})

    def fill(self, tab_id, element_ref, value):
        return self._call("fill", {"tab_id": int(tab_id), "element_ref": element_ref, "value": str(value or "")})

    def select(self, tab_id, element_ref, value):
        return self._call("select", {"tab_id": int(tab_id), "element_ref": element_ref, "value": str(value or "")})

    def press(self, tab_id, key):
        return self._call("press", {
            "tab_id": int(tab_id),
            "key": key,
            # Sem confirmacao configurada, o Enter tambem nao pode ser barrado
            # pelo guard de "submit" da extensao.
            "allow_submit": not confirmar_acoes_arriscadas(),
        })

    def wait(self, tab_id, text="", url_contains="", timeout=10):
        return self._call("wait", {"tab_id": int(tab_id), "text": text, "url_contains": url_contains, "timeout": timeout}, timeout=float(timeout) + 5)

    def back(self, tab_id):
        return self._call("back", {"tab_id": int(tab_id)})

    def screenshot(self, tab_id):
        return self._call("screenshot", {"tab_id": int(tab_id)})

    def click_at(self, tab_id, screenshot_id, x, y, confirmation_token="", expected_label=""):
        return self._call("click_at", {"tab_id": int(tab_id), "screenshot_id": str(screenshot_id), "x": x, "y": y, "confirmation_token": confirmation_token, "expected_label": str(expected_label or "")})

    def download(self, tab_id, element_ref, path="", confirmation_token=""):
        outcome = self._call("download", {"tab_id": int(tab_id), "element_ref": element_ref, "confirmation_token": confirmation_token}, timeout=60)
        if outcome.get("status") == "success" and path:
            source = Path(outcome.get("data", {}).get("file_path", ""))
            target = Path(path).expanduser()
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                outcome["data"]["file_path"] = str(target.resolve())
                outcome["observation"] += f" Arquivo copiado para {target.resolve()}."
            else:
                outcome["status"] = "uncertain"
                outcome["error_code"] = "download_file_missing"
                outcome["retry_hint"] = "Use browser_list_tabs or check Chrome downloads before retrying."
        return outcome

    def search_site(self, tab_id, query, max_pages=5):
        return self._call("search_site", {"tab_id": int(tab_id), "query": query, "max_pages": max_pages}, timeout=120)

    def close(self):
        if self._owns_bridge:
            self._owns_bridge = False
            release_shared_browser_bridge(self.bridge)
