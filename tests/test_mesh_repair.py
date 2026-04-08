import numpy as np
import trimesh
import tempfile
import os
import pytest
from pipeline.mesh_repair import repair_mesh


def make_sphere_obj(path: str, radius=1.0):
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=radius)
    sphere.export(path)


def make_open_mesh_obj(path: str):
    """A sphere with a hole — not watertight."""
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    # Remove some faces to open a hole
    sphere.faces = sphere.faces[20:]
    sphere.export(path)


def test_repair_watertight_sphere():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "sphere.obj")
        dst = os.path.join(tmp, "repaired.obj")
        make_sphere_obj(src)
        repair_mesh(src, dst, target_faces=500)
        result = trimesh.load(dst)
        assert result.is_watertight
        assert len(result.faces) <= 600  # decimated


def test_repair_open_mesh():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "open.obj")
        dst = os.path.join(tmp, "repaired.obj")
        make_open_mesh_obj(src)
        repair_mesh(src, dst, target_faces=500)
        result = trimesh.load(dst)
        assert result.is_watertight


def test_repair_scale_applied():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "sphere.obj")
        dst = os.path.join(tmp, "repaired.obj")
        make_sphere_obj(src, radius=1.0)
        repair_mesh(src, dst, target_faces=500, height_cm=10.0)
        result = trimesh.load(dst)
        height = result.bounds[1][1] - result.bounds[0][1]
        assert abs(height - 10.0) < 0.5  # within 5mm
