"""Developer tools for multi-language projects.

The agent can work with many languages, but execution is always limited to a
working directory inside the user's allowed folders, with bounded output and
timeouts. Package installation and downloads are explicit tools instead of
being hidden side effects of file editing.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests


class DeveloperTools:
    MAX_OUTPUT = 12000
    MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
    DEFAULT_TIMEOUT = 120
    INSTALL_TIMEOUT = 900

    RUNTIME_COMMANDS = {
        "python": ([sys.executable, "--version"], "Python"),
        "node": (["node", "--version"], "Node.js"),
        "npm": (["npm", "--version"], "npm"),
        "pnpm": (["pnpm", "--version"], "pnpm"),
        "yarn": (["yarn", "--version"], "Yarn"),
        "bun": (["bun", "--version"], "Bun"),
        "deno": (["deno", "--version"], "Deno"),
        "go": (["go", "version"], "Go"),
        "rustc": (["rustc", "--version"], "Rust"),
        "cargo": (["cargo", "--version"], "Cargo"),
        "java": (["java", "-version"], "Java"),
        "javac": (["javac", "-version"], "Java compiler"),
        "dotnet": (["dotnet", "--version"], ".NET"),
        "ruby": (["ruby", "--version"], "Ruby"),
        "php": (["php", "--version"], "PHP"),
        "composer": (["composer", "--version"], "Composer"),
        "perl": (["perl", "--version"], "Perl"),
        "lua": (["lua", "-v"], "Lua"),
        "Rscript": (["Rscript", "--version"], "R"),
        "swift": (["swift", "--version"], "Swift"),
        "dart": (["dart", "--version"], "Dart"),
        "elixir": (["elixir", "--version"], "Elixir"),
        "mix": (["mix", "--version"], "Mix"),
        "bash": (["bash", "--version"], "Bash"),
        "powershell": (["powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion"], "PowerShell"),
        "git": (["git", "--version"], "Git"),
        "gcc": (["gcc", "--version"], "GCC"),
        "g++": (["g++", "--version"], "G++"),
        "cmake": (["cmake", "--version"], "CMake"),
        "make": (["make", "--version"], "Make"),
        "mvn": (["mvn", "--version"], "Maven"),
        "gradle": (["gradle", "--version"], "Gradle"),
    }

    EXTENSION_COMMANDS = {
        ".py": "python",
        ".pyw": "python",
        ".js": "node",
        ".mjs": "node",
        ".cjs": "node",
        ".ts": "tsx",
        ".mts": "tsx",
        ".cts": "tsx",
        ".rb": "ruby",
        ".php": "php",
        ".pl": "perl",
        ".lua": "lua",
        ".r": "Rscript",
        ".swift": "swift",
        ".dart": "dart",
        ".ex": "elixir",
        ".exs": "elixir",
        ".fsx": "dotnet-fsi",
        ".csx": "dotnet-script",
        ".sh": "bash",
        ".ps1": "powershell",
        ".bat": "cmd",
        ".cmd": "cmd",
        ".go": "go",
    }

    PACKAGE_MANAGERS = {
        "pip": "python",
        "python": "python",
        "npm": "npm",
        "pnpm": "pnpm",
        "yarn": "yarn",
        "bun": "bun",
        "cargo": "cargo",
        "go": "go",
        "dotnet": "dotnet",
        "gem": "gem",
        "ruby": "gem",
        "composer": "composer",
        "maven": "mvn",
        "gradle": "gradle",
    }

    def __init__(self, file_tools):
        self.file_tools = file_tools

    @staticmethod
    def _clip(value: str, limit: int = MAX_OUTPUT) -> str:
        value = value or ""
        if len(value) <= limit:
            return value
        return value[:limit] + f"\n... [saída cortada em {limit} caracteres]"

    @staticmethod
    def _redact(value: str) -> str:
        text = value or ""
        secret_names = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD")
        for name, secret in os.environ.items():
            if secret and len(secret) >= 8 and any(part in name.upper() for part in secret_names):
                text = text.replace(secret, "[REDACTED]")
        return text

    def _resolve_cwd(self, cwd: str | None) -> Path:
        if cwd and str(cwd).strip() not in {"~", "home", "workspace"}:
            return self.file_tools._resolve_path(cwd)
        candidate = Path.cwd().resolve()
        for root in self.file_tools.allowed_roots:
            try:
                candidate.relative_to(root.resolve())
                return candidate
            except ValueError:
                continue
        return self.file_tools.allowed_roots[0].resolve()

    @staticmethod
    def _blocked_command(command: str) -> str | None:
        normalized = " ".join(str(command).lower().split())
        blocked_fragments = (
            ("git reset --hard", "git reset --hard pode apagar alterações locais"),
            ("git clean -f", "git clean pode apagar arquivos não versionados"),
            ("format ", "formatação de disco não é permitida"),
            ("diskpart", "diskpart não é permitido"),
            ("shutdown", "desligamento do sistema não é permitido"),
            ("restart-computer", "reinicialização do sistema não é permitida"),
            ("remove-item", "remoção via PowerShell não é permitida"),
            ("rm -rf", "remoção recursiva não é permitida"),
            ("rm -r ", "remoção recursiva não é permitida"),
            ("rmdir /s", "remoção recursiva não é permitida"),
            ("del /s", "remoção recursiva não é permitida"),
            ("curl ", "use download_file para downloads controlados"),
            ("wget ", "use download_file para downloads controlados"),
            ("invoke-webrequest", "use download_file para downloads controlados"),
            (".env", "comandos que podem expor .env são bloqueados"),
            ("id_rsa", "acesso a chaves privadas é bloqueado"),
        )
        for fragment, reason in blocked_fragments:
            if fragment in normalized:
                return reason
        return None

    def _run_process(
        self,
        command: list[str] | str,
        cwd: Path,
        timeout: int,
        shell: bool = False,
        input_text: str | None = None,
    ) -> str:
        if isinstance(command, list) and command and os.name == "nt":
            resolved = shutil.which(command[0])
            if resolved and Path(resolved).suffix.lower() in {".cmd", ".bat"}:
                command = ["cmd", "/c", resolved, *command[1:]]
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                input=input_text,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, min(int(timeout), 3600)),
                shell=shell,
                env=os.environ.copy(),
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
            )
        except FileNotFoundError as error:
            return f"Runtime/comando não encontrado: {error}"
        except subprocess.TimeoutExpired as error:
            stdout_text = error.stdout or ""
            stderr_text = error.stderr or ""
            output = self._redact(str(stdout_text) + "\n" + str(stderr_text))
            return f"Processo encerrado por exceder {timeout}s.\n{self._clip(output)}"
        except Exception as error:
            return f"Erro ao executar processo: {error}"

        stdout = self._clip(self._redact(completed.stdout or ""))
        stderr = self._clip(self._redact(completed.stderr or ""))
        status = "success" if completed.returncode == 0 else "failure"
        return (
            f"Exit code: {completed.returncode}\n"
            f"Status: {status}\n"
            f"Código de saída: {completed.returncode}\n"
            f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        )

    def run_terminal(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        input_text: str | None = None,
    ) -> str:
        command = str(command or "").strip()
        if not command:
            return "Informe um comando para executar."
        blocked = self._blocked_command(command)
        if blocked:
            return f"Comando bloqueado por segurança: {blocked}."
        try:
            directory = self._resolve_cwd(cwd)
        except Exception as error:
            return f"Diretório de trabalho inválido: {error}"
        if not directory.exists() or not directory.is_dir():
            return f"Diretório de trabalho não encontrado: {directory}"
        result = self._run_process(command, directory, timeout, shell=True, input_text=input_text)
        return f"Terminal em {directory}\nComando: {command}\n{result}"

    def open_terminal(
        self,
        command: str,
        cwd: str | None = None,
    ) -> str:
        """Abre um CMD visível para o usuário acompanhar a execução."""
        command = str(command or "").strip()
        if not command:
            return "Informe um comando para executar."
        blocked = self._blocked_command(command)
        if blocked:
            return f"Comando bloqueado por segurança: {blocked}."
        try:
            directory = self._resolve_cwd(cwd)
        except Exception as error:
            return f"Diretório de trabalho inválido: {error}"
        if not directory.is_dir():
            return f"Diretório de trabalho não encontrado: {directory}"
        if os.name != "nt":
            return "A abertura de uma janela visível está disponível nesta versão para Windows."
        try:
            subprocess.Popen(
                ["cmd.exe", "/k", command],
                cwd=str(directory),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except Exception as error:
            return f"Não foi possível abrir o terminal: {error}"
        return f"Terminal aberto em {directory}. Comando iniciado: {command}"

    def detect_runtimes(self) -> str:
        rows = []
        for executable, (command, label) in self.RUNTIME_COMMANDS.items():
            location = shutil.which(command[0])
            if not location:
                rows.append(f"[ausente] {label} ({executable})")
                continue
            try:
                probe = command
                if os.name == "nt" and Path(location).suffix.lower() in {".cmd", ".bat"}:
                    probe = ["cmd", "/c", location, *command[1:]]
                result = subprocess.run(
                    probe,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                )
                version = (result.stdout or result.stderr).strip().splitlines()[0] if (result.stdout or result.stderr) else "disponível"
                rows.append(f"[ok] {label}: {version} | {location}")
            except Exception as error:
                rows.append(f"[erro] {label}: {error}")
        return "Runtimes detectados:\n" + "\n".join(rows)

    def _command_for_file(self, file_path: Path, arguments: str) -> list[str] | str | None:
        suffix = file_path.suffix.lower()
        args = shlex.split(arguments or "", posix=False)
        if suffix in {".py", ".pyw"}:
            return [sys.executable, str(file_path), *args]
        if suffix in {".js", ".mjs", ".cjs"}:
            return ["node", str(file_path), *args]
        if suffix in {".ts", ".mts", ".cts"}:
            if shutil.which("tsx"):
                return ["tsx", str(file_path), *args]
            if shutil.which("ts-node"):
                return ["ts-node", str(file_path), *args]
            return None
        if suffix == ".go":
            return ["go", "run", str(file_path), *args]
        if suffix in {".c", ".cc", ".cpp", ".cxx"}:
            compiler = "gcc" if suffix == ".c" else "g++"
            if not shutil.which(compiler):
                return None
            output = file_path.with_name(f".agent_{file_path.stem}_build.exe" if os.name == "nt" else f".agent_{file_path.stem}_build")
            compile_result = self._run_process(
                [compiler, str(file_path), "-O0", "-o", str(output)],
                file_path.parent,
                120,
            )
            if "Código de saída: 0" not in compile_result:
                return ["__compile_failed__", compile_result]
            return [str(output), *args]
        if suffix == ".rs":
            if not shutil.which("rustc"):
                return None
            output = file_path.with_name(f".agent_{file_path.stem}_build.exe" if os.name == "nt" else f".agent_{file_path.stem}_build")
            compile_result = self._run_process(
                ["rustc", str(file_path), "-o", str(output)],
                file_path.parent,
                180,
            )
            if "Código de saída: 0" not in compile_result:
                return ["__compile_failed__", compile_result]
            return [str(output), *args]
        if suffix == ".java":
            if not shutil.which("javac") or not shutil.which("java"):
                return None
            output_dir = Path(tempfile.mkdtemp(prefix="agent-java-", dir=str(file_path.parent)))
            compile_result = self._run_process(
                ["javac", "-d", str(output_dir), str(file_path)],
                file_path.parent,
                180,
            )
            if "Código de saída: 0" not in compile_result:
                return ["__compile_failed__", compile_result]
            return ["java", "-cp", str(output_dir), file_path.stem, *args]
        if suffix in {".kt", ".kts"}:
            runtime = "kotlinc" if suffix == ".kt" else "kotlin"
            if not shutil.which(runtime):
                return None
            return [runtime, str(file_path), *args]
        if suffix == ".scala":
            return ["scala", str(file_path), *args]
        if suffix == ".jl":
            return ["julia", str(file_path), *args]
        if suffix == ".hs":
            return ["runhaskell", str(file_path), *args]
        if suffix in {".rb", ".php", ".pl", ".lua", ".r", ".swift", ".dart", ".ex", ".exs"}:
            runtime = self.EXTENSION_COMMANDS[suffix]
            return [runtime, str(file_path), *args]
        if suffix == ".fsx":
            return ["dotnet", "fsi", str(file_path), *args]
        if suffix in {".ps1"}:
            return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(file_path), *args]
        if suffix in {".bat", ".cmd"}:
            return ["cmd", "/c", str(file_path), *args]
        if suffix == ".sh":
            return ["bash", str(file_path), *args]
        return None

    def run_code_file(
        self,
        path: str,
        arguments: str = "",
        timeout: int = DEFAULT_TIMEOUT,
        input_text: str | None = None,
    ) -> str:
        try:
            file_path = self.file_tools._resolve_path(path)
        except Exception as error:
            return str(error)
        if not file_path.is_file():
            return f"Arquivo não encontrado: {file_path}"
        if input_text is None and file_path.suffix.lower() in {
            ".py", ".js", ".ts", ".rb", ".php", ".pl", ".lua", ".go", ".cs", ".java"
        }:
            try:
                source = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                source = ""
            interactive_pattern = re.compile(
                r"\b(input|readline|readLine|Console\.ReadLine|scanf|gets)\s*\("
            )
            if interactive_pattern.search(source):
                return (
                    "Status: needs_input\n"
                    f"O arquivo {file_path} parece ser interativo e aguarda stdin. "
                    "Execute novamente usando input_text com entradas de teste "
                    "ou forneca argumentos de linha de comando."
                )
        cleanup_targets = []
        if file_path.suffix.lower() in {".c", ".cc", ".cpp", ".cxx", ".rs"}:
            cleanup_targets.append(
                file_path.with_name(
                    f".agent_{file_path.stem}_build.exe" if os.name == "nt" else f".agent_{file_path.stem}_build"
                )
            )
        command = self._command_for_file(file_path, arguments)
        if command is None:
            return (
                f"Não há runtime automático para '{file_path.suffix}'. "
                "Use run_terminal com o comando de build/execução apropriado."
            )
        if command and command[0] == "__compile_failed__":
            return f"Compilação falhou para {file_path}:\n{command[1]}"
        if command and command[0] == "java" and len(command) > 2:
            cleanup_targets.append(Path(command[2]))
        executable = command[0] if isinstance(command, list) else "shell"
        if executable not in {sys.executable, "cmd"} and not shutil.which(executable):
            return f"Runtime '{executable}' não está instalado ou não está no PATH."
        try:
            result = self._run_process(command, file_path.parent, timeout, input_text=input_text)
        finally:
            for target in cleanup_targets:
                try:
                    if target.is_dir():
                        shutil.rmtree(target, ignore_errors=True)
                    elif target.exists():
                        target.unlink()
                except OSError:
                    pass
        return f"Arquivo: {file_path}\n{result}"

    def _manifest_command(self, directory: Path) -> list[str] | None:
        files = {item.name.lower() for item in directory.iterdir() if item.is_file()}
        if "requirements.txt" in files:
            return [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        if "pyproject.toml" in files:
            return [sys.executable, "-m", "pip", "install", "-e", "."]
        if "package.json" in files:
            if shutil.which("pnpm") and (directory / "pnpm-lock.yaml").exists():
                return ["pnpm", "install"]
            if shutil.which("yarn") and (directory / "yarn.lock").exists():
                return ["yarn", "install"]
            return ["npm", "install"]
        if "cargo.toml" in files:
            return ["cargo", "build"]
        if "go.mod" in files:
            return ["go", "mod", "download"]
        if "composer.json" in files:
            return ["composer", "install"]
        if "pom.xml" in files:
            return ["mvn", "dependency:resolve"]
        if "build.gradle" in files or "build.gradle.kts" in files:
            return ["gradle", "build"]
        return None

    def install_dependencies(
        self,
        path: str = "workspace",
        manager: str = "auto",
        packages: str = "",
        dev: bool = False,
        timeout: int = INSTALL_TIMEOUT,
    ) -> str:
        try:
            directory = self._resolve_cwd(path)
        except Exception as error:
            return f"Diretório inválido: {error}"
        if not directory.is_dir():
            return f"Diretório não encontrado: {directory}"

        normalized = (manager or "auto").strip().lower()
        if normalized == "auto":
            command = self._manifest_command(directory)
        else:
            command = None
            tokens = shlex.split(packages or "", posix=False)
            if not tokens:
                return "Informe packages ou use manager=auto para instalar o manifesto do projeto."
            if normalized in {"pip", "python"}:
                command = [sys.executable, "-m", "pip", "install", *tokens]
            elif normalized in {"npm", "pnpm", "yarn", "bun"}:
                command = [normalized, "add", *(["-D"] if dev and normalized in {"npm", "pnpm"} else []), *tokens]
            elif normalized == "cargo":
                command = ["cargo", "add", *tokens]
            elif normalized == "go":
                command = ["go", "get", *tokens]
            elif normalized == "dotnet":
                command = ["dotnet", "add", "package", *tokens]
            elif normalized in {"gem", "ruby"}:
                command = ["gem", "install", *tokens]
            elif normalized == "composer":
                command = ["composer", "require", *tokens]
            else:
                return f"Gerenciador de pacotes não permitido: {manager}"

        if not command:
            return "Não encontrei um manifesto compatível para instalação automática."
        if not shutil.which(command[0]) and command[0] != sys.executable:
            return f"Gerenciador '{command[0]}' não está instalado ou não está no PATH."
        result = self._run_process(command, directory, timeout)
        return f"Instalação em {directory}\nComando: {' '.join(command)}\n{result}"

    def download_file(
        self,
        url: str,
        path: str,
        overwrite: bool = False,
        timeout: int = 120,
    ) -> str:
        parsed = urlparse((url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "Informe uma URL HTTP ou HTTPS válida."
        try:
            target = self.file_tools._resolve_path(path)
        except Exception as error:
            return str(error)
        if target.exists() and not overwrite:
            return f"O arquivo já existe; use overwrite=true para substituir: {target}"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".download.tmp")
        total = 0
        try:
            with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": "AgentePessoal/1.0"}) as response:
                response.raise_for_status()
                length = int(response.headers.get("Content-Length", "0") or 0)
                if length > self.MAX_DOWNLOAD_BYTES:
                    raise ValueError("Download bloqueado: o arquivo excede 100 MB.")
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > self.MAX_DOWNLOAD_BYTES:
                            raise ValueError("Download bloqueado: o arquivo excede 100 MB.")
                        output.write(chunk)
            os.replace(temporary, target)
            return f"Download concluído: {target}\nTamanho: {total} bytes"
        except Exception as error:
            if temporary.exists():
                temporary.unlink()
            return f"Erro no download: {error}"


__all__ = ["DeveloperTools"]
