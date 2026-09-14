from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OperationState:
    objective: str = ""
    files_read: set[str] = field(default_factory=set)
    files_modified: set[str] = field(default_factory=set)
    tools_used: list[str] = field(default_factory=list)
    last_successful_operation: str = ""
    last_error: str = ""
    validation_status: str = "pending"
    execution_status: str = "pending"

    def reset(self, objective: str = ""):
        """Começa uma operação nova sem carregar dados da solicitação anterior."""
        self.objective = str(objective or "")
        self.files_read.clear()
        self.files_modified.clear()
        self.tools_used.clear()
        self.last_successful_operation = ""
        self.last_error = ""
        self.validation_status = "pending"
        self.execution_status = "pending"

    def record_tool(self, name: str):
        self.tools_used.append(name)
        self.tools_used = self.tools_used[-30:]

    def record_success(self, operation: str):
        self.last_successful_operation = operation
        self.last_error = ""

    def record_error(self, error):
        self.last_error = str(error)[:500]

    def record_read(self, path: str):
        self.files_read.add(str(Path(path)))

    def record_modified(self, path: str):
        self.files_modified.add(str(Path(path)))
        self.validation_status = "pending"

    def summary(self) -> str:
        read = "\n".join(f"  - {path}" for path in sorted(self.files_read)) or "  - nenhum"
        modified = "\n".join(f"  - {path}" for path in sorted(self.files_modified)) or "  - nenhum"
        return (
            f"Objetivo: {self.objective or 'nao definido'}\n"
            f"Arquivos lidos ({len(self.files_read)}):\n{read}\n"
            f"Arquivos modificados ({len(self.files_modified)}):\n{modified}\n"
            f"Ferramentas: {', '.join(self.tools_used[-12:]) or 'nenhuma'}\n"
            f"Ultima operacao: {self.last_successful_operation or 'nenhuma'}\n"
            f"Ultimo erro: {self.last_error or 'nenhum'}\n"
            f"Validacao: {self.validation_status}\n"
            f"Execucao: {self.execution_status}"
        )
