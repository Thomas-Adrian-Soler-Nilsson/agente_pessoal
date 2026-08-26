import os
import re
import unicodedata
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None


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
        ".pdf",
        ".docx",
        ".odt",
    }

    def __init__(self):

        home = Path.home()

        self.allowed_roots = [
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
            home / "OneDrive",
        ]

        self.skip_dir_names = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            ".venv-1",
            "dist",
            "build",
            ".mypy_cache",
            ".pytest_cache",
        }

    # ==========================================================
    # VALIDAR CAMINHO
    # ==========================================================

    def _resolve_path(
        self,
        path: str,
    ) -> Path:

        value = (
            os.fspath(path)
            .strip()
            .strip('"')
        )

        normalized = value.replace(
            "/",
            "\\",
        )

        home = Path.home()

        aliases = {
            "downloads": home / "Downloads",
            "download": home / "Downloads",
            "meus downloads": home / "Downloads",
            "pasta downloads": home / "Downloads",
            "onedrive\\downloads": (
                home / "OneDrive" / "Downloads"
            ),
            "unidrive\\downloads": (
                home / "OneDrive" / "Downloads"
            ),
            "anidrive\\downloads": (
                home / "OneDrive" / "Downloads"
            ),
            "anidriving\\downloads": (
                home / "OneDrive" / "Downloads"
            ),
            "onedrive": home / "OneDrive",
            "unidrive": home / "OneDrive",
            "anidrive": home / "OneDrive",
            "anidriving": home / "OneDrive",
        }

        alias = self._normalize_text(
            normalized.strip("\\")
        )

        for alias_name, alias_root in sorted(
            aliases.items(),
            key=lambda item: -len(item[0]),
        ):

            if alias == alias_name:

                value = str(
                    alias_root
                )

                break

            prefix = alias_name + "\\"

            if alias.startswith(prefix):

                value = str(
                    alias_root
                    / normalized[
                        len(prefix):
                    ]
                )

                break

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

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:

        value = unicodedata.normalize(
            "NFKD",
            value,
        )

        value = "".join(
            char
            for char in value
            if not unicodedata.combining(char)
        )

        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip().lower()

    def _is_ignored_path(
        self,
        item: Path,
    ) -> bool:

        return any(
            part.lower()
            in self.skip_dir_names
            for part in item.parts
        )

    @staticmethod
    def _name_matches(
        term: str,
        name: str,
        stem: str,
    ) -> bool:

        if len(term) < 3:

            padded = (
                f"_{stem}_"
            )

            return (
                stem == term
                or name.startswith(
                    f"{term}."
                )
                or padded.find(
                    f"_{term}_"
                ) >= 0
                or padded.find(
                    f"-{term}-"
                ) >= 0
            )

        return (
            term in name
            or term in stem
        )

    # ==========================================================
    # LISTAR
    # ==========================================================

    def list_directory(
        self,
        path: str = "~",
    ) -> str:

        if self._normalize_text(path) in {
            "~",
            "home",
            "pastas permitidas",
        }:

            roots = [
                root
                for root in self.allowed_roots
                if root.exists()
            ]

            if not roots:
                return (
                    "Nenhuma pasta permitida "
                    "está disponível."
                )

            return (
                "Pastas permitidas:\n"
                + "\n".join(
                    f"[PASTA] {root}"
                    for root in roots
                )
            )

        try:

            directory = (
                self._resolve_path(path)
            )

        except Exception as error:

            return str(error)

        if not directory.exists():
            return (
                f"A pasta '{path}' "
                "não existe."
            )

        if not directory.is_dir():
            return (
                f"'{path}' "
                "não é uma pasta."
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
                return (
                    "A pasta está vazia."
                )

            total_entries = len(
                entries
            )

            entries = entries[:100]

            suffix = (
                ""
                if total_entries <= 100
                else (
                    f"\n[Mostrando 100 de "
                    f"{total_entries} itens]"
                )
            )

            return (
                f"Conteúdo de {directory} "
                f"({total_entries} itens):\n"
                + "\n".join(entries)
                + suffix
            )

        except Exception as error:

            return (
                f"Erro ao listar pasta: "
                f"{error}"
            )

    # ==========================================================
    # BUSCAR ARQUIVOS
    # ==========================================================

    def search_files(
        self,
        query: str,
        path: str = "~",
    ) -> str:

        query = self._normalize_text(
            query
        )

        if not query:
            return (
                "Informe o que devo procurar."
            )

        if self._normalize_text(path) in {
            "~",
            "home",
            "pastas permitidas",
            "",
        }:

            roots = [
                root
                for root in self.allowed_roots
                if root.exists()
            ]

            if not roots:
                return (
                    "Nenhuma pasta permitida "
                    "está disponível."
                )

        else:

            try:

                root = self._resolve_path(
                    path
                )

            except Exception as error:

                return str(error)

            if not root.exists():
                return (
                    f"O caminho '{path}' "
                    "não existe."
                )

            roots = [root]

        terms = [
            term
            for term in query.split(" ")
            if term
        ]

        results = []
        seen = set()

        try:

            for root in roots:

                for item in root.rglob("*"):

                    if (
                        not item.is_file()
                        or item.is_symlink()
                        or self._is_ignored_path(
                            item
                        )
                    ):
                        continue

                    resolved = str(
                        item.resolve()
                    )

                    if resolved in seen:
                        continue

                    name = self._normalize_text(
                        item.name
                    )

                    stem = self._normalize_text(
                        item.stem
                    )

                    matched_terms = sum(
                        self._name_matches(
                            term,
                            name,
                            stem,
                        )
                        for term in terms
                    )

                    if matched_terms == len(
                        terms
                    ):

                        seen.add(
                            resolved
                        )

                        results.append(
                            (
                                matched_terms,
                                name,
                                item,
                            )
                        )

        except Exception as error:

            return (
                f"Erro durante a busca: "
                f"{error}"
            )

        results.sort(
            key=lambda result: (
                -result[0],
                result[1],
            )
        )

        results = results[:50]

        if not results:
            return (
                f"Nenhum arquivo encontrado "
                f"para '{query}'."
            )

        return (
            f"Arquivos encontrados para "
            f"'{query}':\n"
            + "\n".join(
                str(item)
                for _, _, item
                in results
            )
        )

    # ==========================================================
    # LER ARQUIVO
    # ==========================================================

    def read_file(
        self,
        path: str,
    ) -> str:

        try:

            file_path = (
                self._resolve_path(path)
            )

        except Exception as error:

            return str(error)

        if not file_path.exists():

            return (
                f"O arquivo '{path}' "
                "não existe."
            )

        if not file_path.is_file():

            return (
                f"'{path}' "
                "não é um arquivo."
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

            if extension == ".pdf":

                if PdfReader is None:
                    return (
                        "Para ler PDF, instale "
                        "a dependência pypdf."
                    )

                reader = PdfReader(
                    str(file_path)
                )

                content = "\n\n".join(
                    page.extract_text() or ""
                    for page in reader.pages
                )

            elif extension == ".docx":

                if Document is None:
                    return (
                        "Para ler DOCX, instale "
                        "a dependência python-docx."
                    )

                document = Document(
                    str(file_path)
                )

                content = "\n\n".join(
                    paragraph.text
                    for paragraph
                    in document.paragraphs
                )

            elif extension == ".odt":

                return (
                    "Leitura de ODT ainda não "
                    "está disponível. Converta "
                    "o arquivo para PDF ou DOCX."
                )

            else:

                content = (
                    file_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                )

            if not content.strip():

                return (
                    f"O arquivo "
                    f"{file_path.name} "
                    "não contém texto extraível."
                )

            max_chars = int(
                os.getenv(
                    "READ_FILE_MAX_CHARS",
                    "12000",
                )
            )

            total_chars = len(
                content
            )

            truncated = (
                total_chars > max_chars
            )

            if truncated:

                returned_content = (
                    content[:max_chars]
                )

                truncation_notice = (
                    "\n\n"
                    "[ARQUIVO TRUNCADO]\n"
                    f"Total de caracteres: "
                    f"{total_chars}\n"
                    f"Caracteres retornados: "
                    f"{max_chars}\n"
                    "Se precisar analisar partes "
                    "posteriores, peça uma leitura "
                    "por faixa ou seção específica."
                )

            else:

                returned_content = (
                    content
                )

                truncation_notice = ""

            return (
                f"Arquivo: {file_path}\n"
                f"Tamanho em caracteres: "
                f"{total_chars}\n\n"
                f"Conteúdo:\n\n"
                f"{returned_content}"
                f"{truncation_notice}"
            )

        except Exception as error:

            return (
                f"Erro ao ler arquivo: "
                f"{error}"
            )

    # ==========================================================
    # ESCREVER / CRIAR ARQUIVO
    # ==========================================================

    def write_file(
        self,
        path: str,
        content: str,
    ) -> str:

        try:
            file_path = self._resolve_path(path)

        except Exception as error:
            return str(error)

        if not path:
            return "Informe o caminho do arquivo."

        if content is None:
            return "O conteúdo do arquivo não foi informado."

        try:
            file_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            file_path.write_text(
                str(content),
                encoding="utf-8",
                newline="",
            )

            return (
                f"Arquivo criado/atualizado com sucesso:\n"
                f"{file_path}\n"
                f"Tamanho: {file_path.stat().st_size} bytes"
            )

        except Exception as error:
            return (
                f"Erro ao escrever arquivo: {error}"
            )

    # ==========================================================
    # INFO
    # ==========================================================

    def get_file_info(
        self,
        path: str,
    ) -> str:

        try:

            file_path = (
                self._resolve_path(path)
            )

        except Exception as error:

            return str(error)

        if not file_path.exists():

            return (
                f"'{path}' "
                "não existe."
            )

        try:

            stat = file_path.stat()

            return (
                f"Arquivo: {file_path}\n"
                f"Tamanho: {stat.st_size} bytes\n"
                f"Extensão: "
                f"{file_path.suffix or 'nenhuma'}\n"
                f"É arquivo: "
                f"{file_path.is_file()}\n"
                f"É pasta: "
                f"{file_path.is_dir()}"
            )

        except Exception as error:

            return (
                f"Erro ao obter informações: "
                f"{error}"
            )
    # ==========================================================
    # EXECUTAR ARQUIVO
    # ==========================================================

    def execute_file(
        self,
        path: str,
    ) -> str:

        import shutil
        import subprocess
        import sys

        try:
            file_path = self._resolve_path(path)

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

        # ------------------------------------------------------
        # PYTHON
        # ------------------------------------------------------

        if extension == ".py":

            try:

                process = subprocess.run(
                    [
                        sys.executable,
                        str(file_path),
                    ],
                    cwd=str(file_path.parent),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                return (
                    f"Execução Python concluída.\n"
                    f"Código de saída: {process.returncode}\n\n"
                    f"STDOUT:\n"
                    f"{process.stdout[-12000:]}\n\n"
                    f"STDERR:\n"
                    f"{process.stderr[-12000:]}"
                )

            except subprocess.TimeoutExpired:
                return (
                    "O programa excedeu o limite de 60 segundos "
                    "e foi encerrado."
                )

            except Exception as error:
                return (
                    f"Erro ao executar Python: {error}"
                )

        # ------------------------------------------------------
        # JAVASCRIPT / NODE
        # ------------------------------------------------------

        if extension == ".js":

            node = shutil.which("node")

            if not node:
                return (
                    "Node.js não está instalado ou não está "
                    "disponível no PATH."
                )

            try:

                process = subprocess.run(
                    [
                        node,
                        str(file_path),
                    ],
                    cwd=str(file_path.parent),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                return (
                    f"Execução Node.js concluída.\n"
                    f"Código de saída: {process.returncode}\n\n"
                    f"STDOUT:\n"
                    f"{process.stdout[-12000:]}\n\n"
                    f"STDERR:\n"
                    f"{process.stderr[-12000:]}"
                )

            except subprocess.TimeoutExpired:
                return (
                    "O programa excedeu o limite de 60 segundos "
                    "e foi encerrado."
                )

            except Exception as error:
                return (
                    f"Erro ao executar JavaScript: {error}"
                )

        # ------------------------------------------------------
        # HTML
        # ------------------------------------------------------

        if extension in {
            ".html",
            ".htm",
        }:

            try:

                os.startfile(
                    str(file_path)
                )

                return (
                    f"Página HTML aberta no navegador:\n"
                    f"{file_path}"
                )

            except Exception as error:

                return (
                    f"Não consegui abrir o HTML: {error}"
                )

        # ------------------------------------------------------
        # ARQUIVOS NÃO EXECUTÁVEIS
        # ------------------------------------------------------

        return (
            f"Não tenho um runtime configurado para "
            f"'{extension}'.\n"
            f"O arquivo foi encontrado em:\n"
            f"{file_path}"
        )