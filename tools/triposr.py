"""Local TripoSR image-to-3D backend.

TripoSR is optional: the repository is configured through TRIPOSR_PATH and is
kept outside this project because its ML dependencies are large and GPU
specific. The integration only starts the official run.py process and copies
the resulting GLB into the user's local output directory.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


OUTPUT_ROOT = Path.home() / "Pictures" / "AgentePessoal" / "TripoSR"


def _repo_path() -> Path:
    raw = os.getenv("TRIPOSR_PATH", "").strip()
    if not raw:
        raise RuntimeError(
            "TripoSR n\u00e3o configurado. Defina TRIPOSR_PATH apontando para o clone do reposit\u00f3rio oficial."
        )
    repo = Path(raw).expanduser().resolve()
    run_file = repo / "run.py"
    if not run_file.is_file():
        raise RuntimeError(f"TRIPOSR_PATH inv\u00e1lido: run.py n\u00e3o encontrado em {repo}")
    return repo


def _viewer(mesh: Path) -> Path | None:
    if mesh.suffix.lower() not in {".glb", ".gltf"}:
        return None
    viewer = mesh.with_suffix(".html")
    viewer.write_text(
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Agente Pessoal - TripoSR</title>"
        "<script type='module' src='https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js'></script>"
        "<style>html,body{margin:0;height:100%;background:#101114}model-viewer{width:100%;height:100%}</style>"
        "</head><body><model-viewer src='" + mesh.as_uri() + "' camera-controls auto-rotate shadow-intensity='1' exposure='1' environment-image='neutral'></model-viewer></body></html>",
        encoding="utf-8",
    )
    return viewer


def generate_triposr(image_path: str, timeout: int | None = None) -> str:
    """Generate a local GLB from one reference image using TripoSR."""
    image = Path(image_path).expanduser().resolve()
    if not image.is_file():
        raise ValueError(f"Imagem de refer\u00eancia n\u00e3o encontrada: {image}")
    if image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("A imagem de refer\u00eancia deve ser PNG, JPG ou WEBP.")

    repo = _repo_path()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    timeout_value = timeout or int(os.getenv("TRIPOSR_TIMEOUT", "900"))
    device = os.getenv("TRIPOSR_DEVICE", "cuda:0")
    python_executable = os.getenv("TRIPOSR_PYTHON", "").strip() or sys.executable

    with tempfile.TemporaryDirectory(prefix="agente_triposr_") as temp_dir:
        output_dir = Path(temp_dir) / "output"
        command = [
            python_executable,
            str(repo / "run.py"),
            str(image),
            "--output-dir",
            str(output_dir),
            "--model-save-format",
            "glb",
            "--device",
            device,
        ]
        if os.getenv("TRIPOSR_BAKE_TEXTURE", "false").strip().lower() in {"1", "true", "yes", "sim"}:
            command.append("--bake-texture")

        try:
            completed = subprocess.run(
                command,
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=timeout_value,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"TripoSR excedeu o limite de {timeout_value}s.") from exc

        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "sem detalhes").strip()
            raise RuntimeError(f"TripoSR falhou ({completed.returncode}): {details[-3000:]}")

        meshes = sorted(output_dir.rglob("*.glb"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not meshes:
            raise RuntimeError("TripoSR terminou sem produzir um arquivo GLB.")

        target = OUTPUT_ROOT / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.glb"
        shutil.copy2(meshes[0], target)

    viewer = _viewer(target)
    suffix = f" Visualizador: {viewer}" if viewer else ""
    return f"Modelo 3D local gerado pelo TripoSR. Arquivo: {target}.{suffix}"


__all__ = ["generate_triposr"]
