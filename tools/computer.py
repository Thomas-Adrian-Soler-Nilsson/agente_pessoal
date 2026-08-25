import os
import shutil
import subprocess
import unicodedata
import webbrowser
from urllib.parse import urlsplit


class ComputerTools:

    APP_ALIASES = {
        # Navegadores
        "chrome": [
            "chrome",
            "google chrome",
        ],
        "google chrome": [
            "chrome",
        ],
        "edge": [
            "msedge",
            "microsoft edge",
        ],

        # Desenvolvimento
        "vscode": [
            "code",
            "visual studio code",
        ],
        "vs code": [
            "code",
        ],
        "visual studio code": [
            "code",
        ],

        # Windows
        "notepad": [
            "notepad",
            "bloco de notas",
        ],
        "calculator": [
            "calc",
            "calculadora",
        ],
        "calculadora": [
            "calc",
        ],
        "explorer": [
            "explorer",
        ],
        "file explorer": [
            "explorer",
        ],
        "explorador de arquivos": [
            "explorer",
        ],
        "gerenciador de tarefas": [
            "taskmgr",
        ],

        # Outros
        "discord": [
            "discord",
        ],
        "spotify": [
            "spotify",
        ],
        "terminal": [
            "wt",
            "cmd",
        ],
    }

    def open_application(
        self,
        application: str,
    ) -> str:

        name = self._normalize_name(application)
        if not name:
            return "Informe qual aplicativo devo abrir."

        candidates = (
            self.APP_ALIASES.get(
                name,
                [name],
            )
        )

        for candidate in candidates:

            executable = shutil.which(
                candidate
            )

            if executable:

                try:

                    subprocess.Popen(
                        [executable],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=(
                            subprocess.CREATE_NEW_PROCESS_GROUP
                            if os.name == "nt"
                            else 0
                        ),
                    )

                    return (
                        f"Aplicativo '{application}' "
                        "aberto com sucesso."
                    )

                except Exception as error:

                    return (
                        f"Encontrei '{candidate}', "
                        f"mas não consegui abrir: {error}"
                    )

        # Tentativa via Windows Shell.
        if os.name == "nt":

            try:
                os.startfile(application)

                return (
                    f"Solicitei ao Windows a abertura "
                    f"de '{application}'."
                )

            except Exception as error:

                return (
                    f"Não consegui abrir "
                    f"'{application}': {error}"
                )

        return (
            f"Não encontrei o aplicativo "
            f"'{application}'."
        )

    def open_directory(self, path: str = "~") -> str:
        if os.name != "nt":
            return "Abrir pastas pelo Explorador só está disponível no Windows."

        value = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
        if not value:
            return "Informe qual pasta devo abrir."
        aliases = {
            "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
            "download": os.path.join(os.path.expanduser("~"), "Downloads"),
            "meus downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
            "pasta downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
            "onedrive\\downloads": os.path.join(os.path.expanduser("~"), "OneDrive", "Downloads"),
            "unidrive\\downloads": os.path.join(os.path.expanduser("~"), "OneDrive", "Downloads"),
            "anidrive\\downloads": os.path.join(os.path.expanduser("~"), "OneDrive", "Downloads"),
            "anidriving\\downloads": os.path.join(os.path.expanduser("~"), "OneDrive", "Downloads"),
            "onedrive": os.path.join(os.path.expanduser("~"), "OneDrive"),
            "unidrive": os.path.join(os.path.expanduser("~"), "OneDrive"),
            "anidrive": os.path.join(os.path.expanduser("~"), "OneDrive"),
            "anidriving": os.path.join(os.path.expanduser("~"), "OneDrive"),
        }
        alias = self._normalize_name(value.replace("/", "\\").strip("\\"))
        directory = aliases.get(alias, value)
        if not os.path.isdir(directory):
            return f"A pasta '{path}' não existe ou não está disponível."

        try:
            subprocess.Popen(
                ["explorer.exe", directory],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            return f"Abri a pasta '{directory}' no Explorador de Arquivos."
        except Exception as error:
            return f"Não consegui abrir a pasta '{path}': {error}"

    @staticmethod
    def _normalize_name(value: str) -> str:
        value = unicodedata.normalize("NFKD", value)
        value = "".join(char for char in value if not unicodedata.combining(char))
        return " ".join(value.strip().lower().split())

    def open_url(
        self,
        url: str,
    ) -> str:

        url = url.strip()
        if not url:
            return "Informe qual URL devo abrir."

        try:
            parsed_input = urlsplit(url)
        except ValueError:
            return "Informe uma URL válida."

        scheme = parsed_input.scheme.lower()
        if scheme and scheme not in {"http", "https"}:
            port_candidate = url.partition(":")[2].split("/", 1)[0]
            if port_candidate.isdigit():
                scheme = ""
            else:
                return "A URL deve usar http:// ou https://."

        if not scheme:
            url = "https://" + url

        try:
            parsed_url = urlsplit(url)
        except ValueError:
            return "Informe uma URL válida."
        if not parsed_url.hostname or any(char.isspace() for char in url):
            return "Informe uma URL válida."

        try:
            opened = webbrowser.open(url)

            if not opened:
                return f"Não consegui abrir {url} no navegador."

            return (
                f"Abri {url} no navegador."
            )

        except Exception as error:

            return (
                f"Não consegui abrir {url}: {error}"
            )
