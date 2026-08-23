import os
import shutil
import subprocess
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

        name = (
            application
            .strip()
            .lower()
        )

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