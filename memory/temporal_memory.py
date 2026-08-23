import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TemporalMemory:
    """
    Memória temporal/persistente do Agente Pessoal.

    Diferente da memória momentânea, esta memória:
    - sobrevive ao fechamento do programa;
    - fica armazenada localmente;
    - pode ser consultada pelo agente;
    - permite atualizar e remover memórias;
    - não depende de banco de dados externo.

    Estrutura:

    memory/
    └── memory.json
    """

    def __init__(self, storage_path: str | None = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = (
                Path(__file__).resolve().parent / "memory.json"
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.data = self._load()

    # ============================================================
    # ARMAZENAMENTO
    # ============================================================

    def _empty_database(self) -> dict[str, Any]:
        return {
            "version": 1,
            "memories": [],
        }

    def _load(self) -> dict[str, Any]:
        """
        Carrega a memória do arquivo JSON.

        Se o arquivo não existir, cria uma estrutura vazia.
        """

        if not self.storage_path.exists():
            data = self._empty_database()
            self._save(data)
            return data

        try:
            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return self._empty_database()

            if "memories" not in data:
                data["memories"] = []

            if "version" not in data:
                data["version"] = 1

            return data

        except (
            json.JSONDecodeError,
            OSError,
        ):
            print(
                "⚠️ Não foi possível ler a memória temporal. "
                "Iniciando uma memória nova."
            )

            return self._empty_database()

    def _save(
        self,
        data: dict[str, Any] | None = None,
    ):
        """
        Salva a memória de forma segura.

        Primeiro escreve em um arquivo temporário e depois substitui
        o arquivo principal. Isso reduz o risco de corromper a memória
        caso o programa seja encerrado durante a gravação.
        """

        if data is None:
            data = self.data

        temporary_path = self.storage_path.with_suffix(
            ".tmp"
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            os.replace(
                temporary_path,
                self.storage_path,
            )

        except OSError as error:
            print(
                f"⚠️ Erro ao salvar memória temporal: {error}"
            )

            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                pass

    # ============================================================
    # UTILITÁRIOS
    # ============================================================

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(
            str(text).strip().lower().split()
        )

    @staticmethod
    def _memory_text(memory: dict[str, Any]) -> str:
        return str(
            memory.get("content", "")
        ).strip()

    # ============================================================
    # ADICIONAR MEMÓRIA
    # ============================================================

    def add(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        """
        Adiciona uma nova memória.

        Se já existir uma memória muito semelhante dentro da mesma
        categoria, ela será atualizada em vez de duplicada.
        """

        content = str(content).strip()
        category = str(category).strip() or "general"

        if not content:
            raise ValueError(
                "Não é possível salvar uma memória vazia."
            )

        importance = max(
            0.0,
            min(1.0, float(importance)),
        )

        normalized_content = self._normalize(
            content
        )

        # Evita duplicações óbvias.
        for memory in self.data["memories"]:
            existing = self._normalize(
                self._memory_text(memory)
            )

            if (
                memory.get("category") == category
                and existing == normalized_content
            ):
                memory["importance"] = importance
                memory["updated_at"] = self._now()
                memory["expires_at"] = expires_at

                self._save()

                return memory

        now = self._now()

        memory = {
            "id": f"mem_{uuid.uuid4().hex[:12]}",
            "category": category,
            "content": content,
            "importance": importance,
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at,
        }

        self.data["memories"].append(
            memory
        )

        self._save()

        return memory

    # ============================================================
    # BUSCAR MEMÓRIA
    # ============================================================

    def search(
        self,
        query: str,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """
        Procura memórias relevantes usando correspondência simples
        de palavras.

        Não utiliza embeddings nem APIs externas nesta primeira versão.
        """

        query = self._normalize(query)

        if not query:
            return []

        query_words = set(
            query.split()
        )

        results = []

        for memory in self.data["memories"]:
            content = self._normalize(
                self._memory_text(memory)
            )

            category = self._normalize(
                memory.get("category", "")
            )

            searchable = (
                f"{content} {category}"
            )

            searchable_words = set(
                searchable.split()
            )

            matches = len(
                query_words & searchable_words
            )

            if matches == 0:
                continue

            score = (
                matches / max(len(query_words), 1)
            )

            # Memórias importantes recebem pequena prioridade.
            score += (
                float(
                    memory.get(
                        "importance",
                        0.5,
                    )
                )
                * 0.1
            )

            results.append(
                (
                    score,
                    memory,
                )
            )

        results.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            memory
            for _, memory in results[:limit]
        ]

    # ============================================================
    # LISTAR
    # ============================================================

    def list_memories(
        self,
        category: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Lista memórias, opcionalmente filtrando por categoria.
        """

        memories = self.data["memories"]

        if category:
            category = self._normalize(
                category
            )

            memories = [
                memory
                for memory in memories
                if self._normalize(
                    memory.get("category", "")
                )
                == category
            ]

        memories = sorted(
            memories,
            key=lambda memory: (
                float(
                    memory.get(
                        "importance",
                        0.5,
                    )
                ),
                memory.get(
                    "updated_at",
                    "",
                ),
            ),
            reverse=True,
        )

        return memories[:limit]

    # ============================================================
    # ATUALIZAR
    # ============================================================

    def update(
        self,
        memory_id: str,
        content: str | None = None,
        category: str | None = None,
        importance: float | None = None,
        expires_at: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Atualiza uma memória existente.
        """

        for memory in self.data["memories"]:
            if memory.get("id") != memory_id:
                continue

            if content is not None:
                content = str(content).strip()

                if not content:
                    raise ValueError(
                        "O conteúdo da memória não pode ficar vazio."
                    )

                memory["content"] = content

            if category is not None:
                category = str(category).strip()

                if category:
                    memory["category"] = category

            if importance is not None:
                memory["importance"] = max(
                    0.0,
                    min(1.0, float(importance)),
                )

            if expires_at is not None:
                memory["expires_at"] = expires_at

            memory["updated_at"] = self._now()

            self._save()

            return memory

        return None

    # ============================================================
    # REMOVER
    # ============================================================

    def delete(
        self,
        memory_id: str,
    ) -> bool:
        """
        Remove uma memória pelo ID.
        """

        original_count = len(
            self.data["memories"]
        )

        self.data["memories"] = [
            memory
            for memory in self.data["memories"]
            if memory.get("id") != memory_id
        ]

        changed = (
            len(self.data["memories"])
            != original_count
        )

        if changed:
            self._save()

        return changed

    # ============================================================
    # LIMPAR
    # ============================================================

    def clear(
        self,
        category: str | None = None,
    ):
        """
        Remove todas as memórias ou somente uma categoria.
        """

        if category is None:
            self.data["memories"] = []
            self._save()
            return

        category = self._normalize(
            category
        )

        self.data["memories"] = [
            memory
            for memory in self.data["memories"]
            if self._normalize(
                memory.get("category", "")
            )
            != category
        ]

        self._save()

    # ============================================================
    # CONTEXTO PARA O LLM
    # ============================================================

    def build_context(
        self,
        query: str | None = None,
        limit: int = 8,
    ) -> str:
        """
        Converte memórias em um bloco de contexto para o LLM.
        """

        if query:
            memories = self.search(
                query,
                limit=limit,
            )
        else:
            memories = self.list_memories(
                limit=limit,
            )

        if not memories:
            return ""

        lines = [
            "===== MEMÓRIA TEMPORAL =====",
            "Informações persistentes conhecidas sobre Thomas:",
        ]

        for memory in memories:
            category = memory.get(
                "category",
                "general",
            )

            content = memory.get(
                "content",
                "",
            )

            lines.append(
                f"- [{category}] {content}"
            )

        lines.append(
            "===== FIM DA MEMÓRIA TEMPORAL ====="
        )

        return "\n".join(lines)

    # ============================================================
    # ESTATÍSTICAS
    # ============================================================

    def count(
        self,
        category: str | None = None,
    ) -> int:
        if category is None:
            return len(
                self.data["memories"]
            )

        category = self._normalize(
            category
        )

        return sum(
            1
            for memory in self.data["memories"]
            if self._normalize(
                memory.get("category", "")
            )
            == category
        )