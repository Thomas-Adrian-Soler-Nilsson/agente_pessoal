import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory.temporal_memory import TemporalMemory


class TemporalMemoryTests(unittest.TestCase):
    def test_similar_memories_are_merged_without_lowering_importance(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = TemporalMemory(Path(directory) / "memory.json")
            first = memory.add("Thomas prefere respostas curtas", "preference", 0.9)
            merged = memory.add("Thomas prefere resposta curta", "preference", 0.4)

            self.assertEqual(first["id"], merged["id"])
            self.assertEqual(memory.count(), 1)
            self.assertEqual(merged["importance"], 0.9)

    def test_expired_memories_are_not_returned_and_are_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = TemporalMemory(Path(directory) / "memory.json")
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            memory.add("Fato temporário", "fact", 0.8, expires_at=past)
            memory.add("Fato permanente", "fact", 0.5)

            results = memory.search("fato")

            self.assertEqual([item["content"] for item in results], ["Fato permanente"])
            self.assertEqual(memory.count(), 1)

    def test_update_list_and_delete_are_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            memory = TemporalMemory(path)
            item = memory.add("Thomas trabalha no projeto", "project", 0.7)
            updated = memory.update(item["id"], content="Thomas mantém o projeto local", importance=1)

            self.assertEqual(updated["importance"], 1)
            self.assertEqual(memory.list_memories()[0]["content"], "Thomas mantém o projeto local")
            self.assertTrue(memory.delete(item["id"]))
            self.assertEqual(memory.count(), 0)

    def test_corrupt_file_is_backed_up_instead_of_silently_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            path.write_text("{not-json", encoding="utf-8")

            memory = TemporalMemory(path)

            self.assertEqual(memory.count(), 0)
            backups = list(Path(directory).glob("memory.corrupt-*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "{not-json")


if __name__ == "__main__":
    unittest.main()
