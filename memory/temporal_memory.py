"""Memória persistente local do Agente Pessoal.

O módulo é deliberadamente pequeno e não depende de banco externo. A memória
é usada como uma base de fatos estáveis, não como uma cópia da conversa.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import unicodedata
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from ui import ui


STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "um", "uma",
    "uns", "umas", "e", "é", "ou", "que", "com", "para", "por", "em",
    "no", "na", "nos", "nas", "sobre", "como", "isso", "essa", "esse",
    "esses", "essas", "este", "esta", "estes", "estas", "meu", "minha",
    "meus", "minhas", "seu", "sua", "seus", "suas", "eu", "voce", "ele",
    "ela", "eles", "elas", "ao", "aos", "se", "ja", "mais", "muito",
    "tambem", "foi", "ser", "tem", "tinha", "estava", "estou", "fica",
    "ficou", "quero", "queria", "pode", "poderia", "vai", "vou",
}


class TemporalMemory:
    """Memória persistente com deduplicação, expiração e busca ranqueada."""

    CURRENT_VERSION = 2

    def __init__(self, storage_path: str | None = None):
        self.storage_path = Path(storage_path) if storage_path else (
            Path(__file__).resolve().parent / "memory.json"
        )
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.data = self._load()

    # ============================================================
    # ARMAZENAMENTO SEGURO
    # ============================================================

    @staticmethod
    def _empty_database() -> dict[str, Any]:
        return {"version": TemporalMemory.CURRENT_VERSION, "memories": []}

    def _load(self) -> dict[str, Any]:
        if not self.storage_path.exists():
            data = self._empty_database()
            self._save(data)
            return data

        try:
            with self.storage_path.open("r", encoding="utf-8") as file:
                raw = json.load(file)
        except (json.JSONDecodeError, OSError, UnicodeError) as error:
            # A memória anterior não é apagada: fica uma cópia recuperável
            # para inspeção manual caso um desligamento tenha interrompido a escrita.
            backup = self.storage_path.with_name(
                f"{self.storage_path.stem}.corrupt-{self._stamp_for_filename()}.json"
            )
            try:
                shutil.copy2(self.storage_path, backup)
            except OSError:
                backup = None
            ui.warn(
                "Memória temporal inválida; uma base nova será usada. "
                + (f"Cópia: {backup}" if backup else "")
            )
            return self._empty_database()

        if not isinstance(raw, dict):
            ui.warn("Formato de memória temporal inválido; usando base nova.")
            return self._empty_database()

        memories = raw.get("memories", [])
        if not isinstance(memories, list):
            memories = []

        normalized = []
        seen = set()
        for item in memories:
            if not isinstance(item, dict):
                continue
            memory = self._normalize_record(item)
            if not memory:
                continue
            # Corrige duplicatas herdadas do formato antigo na carga, sem
            # alterar o texto escolhido pelo usuário.
            key = (memory["category"], self._normalize(memory["content"]))
            if key in seen:
                continue
            seen.add(key)
            normalized.append(memory)

        return {
            "version": self.CURRENT_VERSION,
            "memories": normalized,
        }

    @staticmethod
    def _stamp_for_filename() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    def _save(self, data: dict[str, Any] | None = None):
        payload = data if data is not None else self.data
        temporary_path = None
        try:
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{self.storage_path.name}.",
                suffix=".tmp",
                dir=str(self.storage_path.parent),
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.storage_path)
        except OSError as error:
            ui.error(f"Erro ao salvar memória temporal: {error}")
            if temporary_path and temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    # ============================================================
    # NORMALIZAÇÃO E EXPIRAÇÃO
    # ============================================================

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize(text: str) -> str:
        value = str(text or "").strip().lower()
        value = unicodedata.normalize("NFKD", value)
        value = "".join(char for char in value if not unicodedata.combining(char))
        return " ".join(value.split())

    @classmethod
    def _tokens(cls, text: str) -> list[str]:
        return [word for word in cls._normalize(text).split() if word]

    @classmethod
    def _category(cls, category: str) -> str:
        return cls._normalize(category) or "general"

    @classmethod
    def _normalize_record(cls, item: dict[str, Any]) -> dict[str, Any] | None:
        content = str(item.get("content", "")).strip()
        if not content:
            return None
        try:
            importance = float(item.get("importance", 0.5))
        except (TypeError, ValueError):
            importance = 0.5
        importance = max(0.0, min(1.0, importance))
        now = cls._now()
        return {
            "id": str(item.get("id") or f"mem_{uuid.uuid4().hex[:12]}"),
            "category": cls._category(item.get("category", "general")),
            "content": content,
            "importance": importance,
            "created_at": str(item.get("created_at") or now),
            "updated_at": str(item.get("updated_at") or now),
            "expires_at": item.get("expires_at"),
        }

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return None

    @classmethod
    def _is_expired(cls, memory: dict[str, Any]) -> bool:
        expires_at = cls._parse_datetime(memory.get("expires_at"))
        return expires_at is not None and expires_at <= datetime.now(timezone.utc)

    def _active_memories(self, persist_cleanup: bool = True) -> list[dict[str, Any]]:
        with self._lock:
            active = [memory for memory in self.data["memories"] if not self._is_expired(memory)]
            if len(active) != len(self.data["memories"]):
                self.data["memories"] = active
                if persist_cleanup:
                    self._save()
            return active

    @staticmethod
    def _copy(memory: dict[str, Any]) -> dict[str, Any]:
        return dict(memory)

    # ============================================================
    # ADICIONAR E DEDUPLICAR
    # ============================================================

    @classmethod
    def _similarity(cls, first: str, second: str) -> float:
        a = cls._normalize(first)
        b = cls._normalize(second)
        if a == b:
            return 1.0
        ratio = SequenceMatcher(None, a, b).ratio()
        first_tokens = set(cls._tokens(a)) - STOPWORDS
        second_tokens = set(cls._tokens(b)) - STOPWORDS
        if not first_tokens or not second_tokens:
            return ratio
        jaccard = len(first_tokens & second_tokens) / len(first_tokens | second_tokens)
        return max(ratio, jaccard)

    def add(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        content = str(content or "").strip()
        if not content:
            raise ValueError("Não é possível salvar uma memória vazia.")
        category = self._category(category)
        try:
            importance = float(importance)
        except (TypeError, ValueError):
            importance = 0.5
        importance = max(0.0, min(1.0, importance))
        if expires_at is not None and self._parse_datetime(expires_at) is None:
            raise ValueError("expires_at precisa ser uma data ISO válida.")

        with self._lock:
            self._active_memories()
            for memory in self.data["memories"]:
                if memory.get("category") != category:
                    continue
                if self._similarity(memory.get("content", ""), content) < 0.94:
                    continue
                # Atualiza a memória existente em vez de criar outra. Um
                # texto novo só substitui o antigo quando traz mais contexto.
                if len(content) > len(memory.get("content", "")):
                    memory["content"] = content
                memory["importance"] = max(float(memory.get("importance", 0.5)), importance)
                if expires_at is not None:
                    memory["expires_at"] = expires_at
                memory["updated_at"] = self._now()
                self._save()
                return self._copy(memory)

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
            self.data["memories"].append(memory)
            self._save()
            return self._copy(memory)

    # ============================================================
    # BUSCA RANQUEADA
    # ============================================================

    @classmethod
    def _words_match(cls, query_word: str, candidate_word: str) -> bool:
        if query_word == candidate_word:
            return True
        if len(query_word) >= 4 and len(candidate_word) >= 4:
            if query_word.startswith(candidate_word) or candidate_word.startswith(query_word):
                return True
            return SequenceMatcher(None, query_word, candidate_word).ratio() >= 0.84
        return False

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        query_normalized = self._normalize(query)
        if not query_normalized:
            return []
        try:
            limit = max(1, min(20, int(limit)))
        except (TypeError, ValueError):
            limit = 8

        raw_words = self._tokens(query_normalized)
        query_words = [word for word in raw_words if word not in STOPWORDS] or raw_words
        ranked = []
        for memory in self._active_memories():
            content = self._normalize(memory.get("content", ""))
            category = self._normalize(memory.get("category", ""))
            candidate_words = set(self._tokens(f"{content} {category}"))
            matched = sum(
                1 for word in query_words
                if any(self._words_match(word, candidate) for candidate in candidate_words)
            )
            if not matched:
                continue

            coverage = matched / len(query_words)
            phrase = 1.0 if query_normalized in content else 0.0
            query_set = set(query_words)
            candidate_set = set(self._tokens(content))
            jaccard = len(query_set & candidate_set) / max(1, len(query_set | candidate_set))
            importance = float(memory.get("importance", 0.5))
            # Importância domina pequenas diferenças de data, mas memórias
            # recém-confirmadas vencem empates antigos.
            freshness = 0.0
            updated = self._parse_datetime(memory.get("updated_at"))
            if updated:
                age_days = max(0.0, (datetime.now(timezone.utc) - updated).total_seconds() / 86400)
                freshness = 1.0 / (1.0 + age_days / 30.0)
            score = coverage * 0.62 + jaccard * 0.16 + phrase * 0.10 + importance * 0.08 + freshness * 0.04
            ranked.append((score, importance, memory.get("updated_at", ""), memory))

        ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [self._copy(memory) for _, _, _, memory in ranked[:limit]]

    # ============================================================
    # LISTAR, ATUALIZAR E REMOVER
    # ============================================================

    def list_memories(self, category: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        try:
            limit = max(1, min(100, int(limit)))
        except (TypeError, ValueError):
            limit = 50
        memories = self._active_memories()
        if category:
            wanted = self._category(category)
            memories = [memory for memory in memories if memory.get("category") == wanted]
        memories = sorted(
            memories,
            key=lambda memory: (float(memory.get("importance", 0.5)), memory.get("updated_at", "")),
            reverse=True,
        )
        return [self._copy(memory) for memory in memories[:limit]]

    def update(
        self,
        memory_id: str,
        content: str | None = None,
        category: str | None = None,
        importance: float | None = None,
        expires_at: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            self._active_memories()
            for memory in self.data["memories"]:
                if memory.get("id") != memory_id:
                    continue
                if content is not None:
                    content = str(content).strip()
                    if not content:
                        raise ValueError("O conteúdo da memória não pode ficar vazio.")
                    memory["content"] = content
                if category is not None and str(category).strip():
                    memory["category"] = self._category(category)
                if importance is not None:
                    try:
                        memory["importance"] = max(0.0, min(1.0, float(importance)))
                    except (TypeError, ValueError):
                        raise ValueError("importance precisa ser um número entre 0 e 1.")
                if expires_at is not None:
                    if self._parse_datetime(expires_at) is None:
                        raise ValueError("expires_at precisa ser uma data ISO válida.")
                    memory["expires_at"] = expires_at
                memory["updated_at"] = self._now()
                self._save()
                return self._copy(memory)
        return None

    def delete(self, memory_id: str) -> bool:
        with self._lock:
            self._active_memories()
            before = len(self.data["memories"])
            self.data["memories"] = [m for m in self.data["memories"] if m.get("id") != memory_id]
            if len(self.data["memories"]) == before:
                return False
            self._save()
            return True

    def clear(self, category: str | None = None):
        with self._lock:
            self._active_memories()
            if category is None:
                self.data["memories"] = []
            else:
                wanted = self._category(category)
                self.data["memories"] = [m for m in self.data["memories"] if m.get("category") != wanted]
            self._save()

    # ============================================================
    # CONTEXTO E ESTATÍSTICAS
    # ============================================================

    def build_context(self, query: str | None = None, limit: int = 8, max_chars: int = 6000) -> str:
        memories = self.search(query, limit) if query else self.list_memories(limit=limit)
        if not memories:
            return ""
        try:
            max_chars = max(500, int(max_chars))
        except (TypeError, ValueError):
            max_chars = 6000
        lines = [
            "===== MEMORIA TEMPORAL =====",
            "Fatos persistentes relevantes sobre Thomas (use apenas quando ajudarem):",
        ]
        used = sum(len(line) + 1 for line in lines)
        for memory in memories:
            line = f"- [{memory.get('category', 'general')}] {memory.get('content', '')}"
            if used + len(line) + 1 > max_chars:
                break
            lines.append(line)
            used += len(line) + 1
        lines.append("===== FIM DA MEMORIA TEMPORAL =====")
        return "\n".join(lines)

    def count(self, category: str | None = None) -> int:
        memories = self._active_memories()
        if category is not None:
            wanted = self._category(category)
            memories = [memory for memory in memories if memory.get("category") == wanted]
        return len(memories)
