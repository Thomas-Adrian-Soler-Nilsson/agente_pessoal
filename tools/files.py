import os
from pathlib import Path


class FileTools:

    ALLOWED_EXTENSIONS = {
        ".txt",
        ".md",
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".json",
        ".csv",
        ".xml",
        ".html",
        ".css",
        ".sql",
        ".yaml",
        ".yml",
        ".log",
        ".ini",
        ".env",
    }

    def __init__(self):

        home = Path.home()

        self.allowed_roots = [
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
            home / "OneDrive",
        ]

    # ==========================================================
    # VALIDAR CAMINHO
    # ==========================================================

    def _resolve_path(
        self,
        path: str,
    ) -> Path:

        value = os.fspath(path).strip().strip('"')
        normalized = value.replace("/", "\\")
        home = Path.home()
        aliases = {
            "downloads": home / "Downloads",
            "download": home / "Downloads",
            "onedrive\\downloads": home / "OneDrive" / "Downloads",
            "unidrive\\downloads": home / "OneDrive" / "Downloads",
            "onedrive": home / "OneDrive",
            "unidrive": home / "OneDrive",
        }
        alias = normalized.strip("\\").lower()
        if alias in aliases:
            value = str(aliases[alias])

        candidate = (
            Path(value)
            .expanduser()
            .resolve()
        )

        for root in self.allowed_roots:

            try:

                candidate.relative_to(
                    root.resolve()
                )

                return candidate

            except ValueError:
                continue

        raise PermissionError(
            "Esse caminho está fora das "
            "pastas permitidas pelo agente."
        )

    # ==========================================================
    # LISTAR
    # ==========================================================

    def list_directory(
        self,
        path: str = "~",
    ) -> str:

        try:

            directory = self._resolve_path(
                path
            )

        except Exception as error:

            return str(error)

        if not directory.exists():

            return (
                f"A pasta '{path}' não existe."
            )

        if not directory.is_dir():

            return (
                f"'{path}' não é uma pasta."
            )

        try:

            entries = []

            for item in sorted(
                directory.iterdir(),
                key=lambda x: (
                    not x.is_dir(),
                    x.name.lower(),
                ),
            ):

                if item.is_dir():

                    entries.append(
                        f"[PASTA] {item.name}"
                    )

                else:

                    entries.append(
                        f"[ARQUIVO] {item.name}"
                    )

            if not entries:

                return "A pasta está vazia."

            # Evita contexto gigante.
            entries = entries[:100]

            return (
                f"Conteúdo de {directory}:\n"
                + "\n".join(entries)
            )

        except Exception as error:

            return (
                f"Erro ao listar pasta: {error}"
            )

    # ==========================================================
    # BUSCAR ARQUIVOS
    # ==========================================================

    def search_files(
        self,
        query: str,
        path: str = "~",
    ) -> str:

        try:

            root = self._resolve_path(
                path
            )

        except Exception as error:

            return str(error)

        if not root.exists():

            return (
                f"O caminho '{path}' não existe."
            )

        query = (
            query
            .strip()
            .lower()
        )

        if not query:

            return (
                "Informe o que devo procurar."
            )

        results = []

        try:

            for item in root.rglob("*"):

                if not item.is_file():
                    continue

                if (
                    query
                    in item.name.lower()
                ):

                    results.append(
                        str(item)
                    )

                if len(results) >= 50:
                    break

        except Exception as error:

            return (
                f"Erro durante a busca: {error}"
            )

        if not results:

            return (
                f"Nenhum arquivo encontrado "
                f"para '{query}'."
            )

        return (
            f"Arquivos encontrados para "
            f"'{query}':\n"
            + "\n".join(results)
        )

    # ==========================================================
    # LER ARQUIVO
    # ==========================================================

    def read_file(
        self,
        path: str,
    ) -> str:

        try:

            file_path = self._resolve_path(
                path
            )

        except Exception as error:

            return str(error)

        if not file_path.exists():

            return (
                f"O arquivo '{path}' não existe."
            )

        if not file_path.is_file():

            return (
                f"'{path}' não é um arquivo."
            )

        extension = (
            file_path.suffix.lower()
        )

        if extension not in self.ALLOWED_EXTENSIONS:

            return (
                f"Por segurança, ainda não "
                f"consigo ler arquivos do tipo "
                f"'{extension}'."
            )

        try:

            content = (
                file_path
                .read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            )

            # Não despejar arquivos gigantes
            # no contexto do Gemini.
            max_chars = 30000

            if len(content) > max_chars:

                content = (
                    content[:max_chars]
                    + "\n\n[ARQUIVO TRUNCADO]"
                )

            return (
                f"Conteúdo de {file_path}:\n\n"
                f"{content}"
            )

        except Exception as error:

            return (
                f"Erro ao ler arquivo: {error}"
            )

    # ==========================================================
    # INFO
    # ==========================================================

    def get_file_info(
        self,
        path: str,
    ) -> str:

        try:

            file_path = self._resolve_path(
                path
            )

        except Exception as error:

            return str(error)

        if not file_path.exists():

            return (
                f"'{path}' não existe."
            )

        try:

            stat = file_path.stat()

            return (
                f"Arquivo: {file_path}\n"
                f"Tamanho: {stat.st_size} bytes\n"
                f"Extensão: {file_path.suffix or 'nenhuma'}\n"
                f"É arquivo: {file_path.is_file()}\n"
                f"É pasta: {file_path.is_dir()}"
            )

        except Exception as error:

            return (
                f"Erro ao obter informações: {error}"
            )