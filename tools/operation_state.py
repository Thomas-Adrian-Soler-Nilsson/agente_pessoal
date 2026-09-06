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
        return (
            f"Objetivo: {self.objective or 'não definido'}\n"
            f"Arquivos lidos: {len(self.files_read)}\n"
            f"Arquivos modificados: {len(self.files_modified)}\n"
            f"Última operação: {self.last_successful_operation or 'nenhuma'}\n"
            f"Último erro: {self.last_error or 'nenhum'}\n"
            f"Validação: {self.validation_status}\n"
            f"Execução: {self.execution_status}"
        )
