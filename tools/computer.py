import os
import shutil
import subprocess
import unicodedata
import webbrowser


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

                subprocess.Popen(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        "Start-Process",
                        application,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

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

        if not (
            url.startswith("http://")
            or url.startswith("https://")
        ):
            url = "https://" + url

        try:

            webbrowser.open(url)

            return (
                f"Abri {url} no navegador."
            )

        except Exception as error:

            return (
                f"Não consegui abrir {url}: {error}"
            )