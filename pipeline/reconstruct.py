# pipeline/reconstruct.py
"""
TripoSR reconstruction stub.

TripoSR (stabilityai/TripoSR) could not be installed in this environment.
The project venv runs Python 3.14, and torch is not available for Python 3.14
at the time of setup. TripoSR's repo also ships without setup.py/pyproject.toml,
so it cannot be pip-installed directly.

To enable real reconstruction, set up a Python 3.11 venv with torch:
  python3.11 -m venv .venv311
  source .venv311/bin/activate
  pip install torch torchvision
  pip install omegaconf einops transformers huggingface-hub trimesh
  git clone https://github.com/VAST-AI-Research/TripoSR.git /tmp/TripoSR
  # Then use sys.path.insert(0, '/tmp/TripoSR') in reconstruct.py

This stub creates a sphere OBJ so the rest of the pipeline can be built and tested.
"""
from __future__ import annotations
import trimesh
import numpy as np


def reconstruct(image_paths: list[str], out_path: str) -> None:
    """
    STUB: generates a sphere mesh for pipeline testing.
    Replace with real TripoSR inference when torch + TripoSR are available.

    Args:
        image_paths: Ignored in stub mode.
        out_path:    Absolute path for output .obj file.
    """
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    sphere.export(out_path)
