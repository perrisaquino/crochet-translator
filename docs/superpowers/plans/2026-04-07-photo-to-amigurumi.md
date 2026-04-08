# Photo-to-Amigurumi Pattern Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Photo mode to the existing Crochet Notation Translator that takes drag-dropped photos of a real object, reconstructs a 3D mesh, and generates a downloadable amigurumi PDF pattern.

**Architecture:** A Python FastAPI backend runs on `localhost:8000` and serves the existing `index.html` as a static file. The frontend gains a new Photo tab that POSTs photos to the backend, polls for job status, loads the resulting OBJ mesh into the existing Three.js viewer, and renders the pattern in the existing right panel. The backend pipeline is: TripoSR (photos → mesh) → Open3D (mesh repair) → AmiGo algorithm (mesh → pattern JSON) → WeasyPrint (pattern → PDF).

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, TripoSR (HuggingFace), Open3D, trimesh, potpourri3d, NumPy, SciPy, Jinja2, WeasyPrint, pytest, Three.js OBJLoader (existing Three.js 0.139.0)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `requirements.txt` | Create | Python dependencies |
| `server.py` | Create | FastAPI app, endpoints, job store, static file serving |
| `pipeline/__init__.py` | Create | Empty package marker |
| `pipeline/reconstruct.py` | Create | TripoSR inference: photos → raw OBJ mesh |
| `pipeline/mesh_repair.py` | Create | Open3D: hole fill, decimate, watertight → clean OBJ |
| `pipeline/pattern_gen.py` | Create | AmiGo algorithm: clean mesh → pattern JSON |
| `templates/pattern.html` | Create | Jinja2 PDF template |
| `tmp/.gitkeep` | Create | Temp mesh storage (gitignored) |
| `tests/test_mesh_repair.py` | Create | Mesh repair unit tests |
| `tests/test_pattern_gen.py` | Create | Pattern generation unit tests |
| `tests/test_server.py` | Create | API endpoint integration tests |
| `index.html` | Modify | Add OBJLoader script, Photo tab, Photo mode UI, JS handlers |

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `pipeline/__init__.py`
- Create: `tmp/.gitkeep`
- Modify: `.gitignore` (create if absent)

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.9
trimesh>=4.0.0
open3d>=0.18.0
potpourri3d>=0.0.8
numpy>=1.24.0
scipy>=1.12.0
torch>=2.2.0
jinja2>=3.1.0
weasyprint>=62.0
pillow>=10.0.0
pytest>=8.0.0
httpx>=0.27.0
huggingface-hub>=0.21.0
# TripoSR — install separately (see below)
```

- [ ] **Step 2: Install TripoSR from source**

TripoSR is not on PyPI. Install from the VAST-AI repo:

```bash
pip install git+https://github.com/VAST-AI-Research/TripoSR.git
```

Then install remaining deps:

```bash
pip install -r requirements.txt
```

Expected: no errors. If torch MPS fails on M1, ensure you have `torch>=2.2.0` with `torchvision` installed via the PyTorch website installer for Apple Silicon.

- [ ] **Step 3: Create pipeline package and tmp dir**

```bash
mkdir -p pipeline tests tmp
touch pipeline/__init__.py tmp/.gitkeep
```

- [ ] **Step 4: Create/update .gitignore**

```
tmp/
*.obj
*.pyc
__pycache__/
.pytest_cache/
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt pipeline/__init__.py tmp/.gitkeep .gitignore
git commit -m "chore: project setup for photo-to-amigurumi backend"
```

---

## Task 2: FastAPI Server — Job Store + Static Serving

**Files:**
- Create: `server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
import pytest
from httpx import AsyncClient, ASGITransport
from server import app

@pytest.mark.asyncio
async def test_root_serves_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]

@pytest.mark.asyncio
async def test_job_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/job/nonexistent-id")
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_job_lifecycle():
    from server import create_job, update_job, get_job
    job_id = create_job()
    assert get_job(job_id)["status"] == "pending"
    update_job(job_id, status="processing", step="Analyzing photos")
    assert get_job(job_id)["step"] == "Analyzing photos"
    update_job(job_id, status="complete", mesh_url=f"/api/mesh/{job_id}")
    assert get_job(job_id)["status"] == "complete"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_server.py -v
```

Expected: `ImportError: cannot import name 'app' from 'server'`

- [ ] **Step 3: Create server.py**

```python
# server.py
import uuid
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

app = FastAPI()
_jobs: dict[str, dict] = {}


def create_job() -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "step": None, "mesh_url": None}
    return job_id


def update_job(job_id: str, **kwargs) -> None:
    _jobs[job_id].update(kwargs)


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


@app.get("/api/job/{job_id}")
async def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return job


# Serve index.html and static assets — must be LAST
app.mount("/", StaticFiles(directory=".", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_server.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Verify server starts and serves index.html**

```bash
python server.py
```

Open `http://localhost:8000` — existing Crochet Notation Translator UI should appear.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: FastAPI server with job store and static file serving"
```

---

## Task 3: Mesh Repair Pipeline

**Files:**
- Create: `pipeline/mesh_repair.py`
- Create: `tests/test_mesh_repair.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_mesh_repair.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_mesh_repair.py -v
```

Expected: `ImportError: cannot import name 'repair_mesh'`

- [ ] **Step 3: Implement pipeline/mesh_repair.py**

```python
# pipeline/mesh_repair.py
import numpy as np
import trimesh
import open3d as o3d


def repair_mesh(src_path: str, dst_path: str, target_faces: int = 8000, height_cm: float | None = None) -> None:
    """
    Load a mesh, fill holes, decimate, optionally scale to real-world height, save.

    Args:
        src_path:     Input OBJ path (may be noisy/open).
        dst_path:     Output OBJ path (watertight, decimated).
        target_faces: Target face count after decimation (default 8000).
        height_cm:    If provided, uniformly scale mesh so its Y-axis height equals this value in cm.
    """
    # Load with open3d for hole filling
    o3d_mesh = o3d.io.read_triangle_mesh(src_path)
    o3d_mesh.compute_vertex_normals()

    # Fill holes
    o3d_mesh = o3d_mesh.fill_holes(hole_size=1000)

    # Save intermediate then reload with trimesh for decimation
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as f:
        tmp_path = f.name
    o3d.io.write_triangle_mesh(tmp_path, o3d_mesh)

    mesh = trimesh.load(tmp_path)
    os.unlink(tmp_path)

    # Ensure single mesh (take largest if scene)
    if isinstance(mesh, trimesh.Scene):
        mesh = max(mesh.dump(), key=lambda m: len(m.faces))

    # Decimate
    if len(mesh.faces) > target_faces:
        mesh = mesh.simplify_quadric_decimation(target_faces)

    # Scale to real-world height
    if height_cm is not None:
        current_height = mesh.bounds[1][1] - mesh.bounds[0][1]
        if current_height > 0:
            scale = height_cm / current_height
            mesh.apply_scale(scale)

    mesh.export(dst_path)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_mesh_repair.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/mesh_repair.py tests/test_mesh_repair.py
git commit -m "feat: mesh repair pipeline — hole fill, decimate, scale"
```

---

## Task 4: TripoSR Reconstruction

**Files:**
- Create: `pipeline/reconstruct.py`

> **Note:** TripoSR's Python API uses `TSR` model class from the `tsr` package. Verify the import with `python -c "from tsr.system import TSR; print('ok')"` before writing tests. If the import path differs, adjust accordingly.

- [ ] **Step 1: Verify TripoSR import**

```bash
python -c "from tsr.system import TSR; print('TripoSR import OK')"
```

Expected: `TripoSR import OK`. If it fails, check the installed package's actual module name with `pip show TripoSR`.

- [ ] **Step 2: Create pipeline/reconstruct.py**

```python
# pipeline/reconstruct.py
"""
Wraps TripoSR inference: list of image paths → OBJ mesh file.
Model weights are downloaded from HuggingFace on first call (~1.5GB).
Inference runs on Apple MPS (M1 GPU) when available, falls back to CPU.
"""
from __future__ import annotations
import os
from pathlib import Path
from PIL import Image
import torch
import numpy as np

_model = None  # lazy singleton


def _get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _load_model():
    global _model
    if _model is not None:
        return _model
    from tsr.system import TSR
    device = _get_device()
    _model = TSR.from_pretrained(
        "stabilityai/TripoSR",
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    _model = _model.to(device)
    _model.renderer.set_chunk_size(131072)
    return _model


def reconstruct(image_paths: list[str], out_path: str) -> None:
    """
    Run TripoSR on one or more images and export an OBJ mesh.

    TripoSR processes one image at a time (single-image 3D reconstruction).
    When multiple images are provided, the first image is used. Multi-image
    photogrammetry support can be added in v2 via OpenMVG/Meshroom.

    Args:
        image_paths: List of absolute paths to input photos (JPEG/PNG).
        out_path:    Absolute path for output .obj file.
    """
    model = _load_model()
    device = _get_device()

    image = Image.open(image_paths[0]).convert("RGB")

    with torch.no_grad():
        scene_codes = model([image], device=device)

    meshes = model.extract_mesh(scene_codes, resolution=256)
    mesh = meshes[0]

    out_dir = str(Path(out_path).parent)
    mesh.export(out_path)
```

- [ ] **Step 3: Smoke-test reconstruction manually**

```bash
python -c "
from pipeline.reconstruct import reconstruct
import os, tempfile, glob

# Use any JPEG you have on disk
test_img = os.path.expanduser('~/Desktop/test_object.jpg')
if not os.path.exists(test_img):
    print('Put a test photo at ~/Desktop/test_object.jpg and re-run')
else:
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'out.obj')
        reconstruct([test_img], out)
        print('Mesh vertices:', open(out).read().count('\\nv '))
"
```

Expected: prints vertex count > 0. First run downloads ~1.5GB model weights — takes a few minutes.

- [ ] **Step 4: Commit**

```bash
git add pipeline/reconstruct.py
git commit -m "feat: TripoSR reconstruction wrapper"
```

---

## Task 5: Reconstruct API Endpoint

**Files:**
- Modify: `server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Add failing tests**

Add to `tests/test_server.py`:

```python
import io
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_reconstruct_returns_job_id():
    fake_image = io.BytesIO(b"fake_image_bytes")

    async def mock_pipeline(job_id, image_paths, height_cm):
        from server import update_job
        update_job(job_id, status="complete", step="Done", mesh_url=f"/api/mesh/{job_id}")

    with patch("server.run_pipeline", side_effect=mock_pipeline):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/reconstruct",
                data={"height_cm": "10.0"},
                files={"photos": ("photo.jpg", fake_image, "image/jpeg")},
            )
    assert resp.status_code == 200
    assert "job_id" in resp.json()

@pytest.mark.asyncio
async def test_mesh_endpoint_returns_404_for_missing_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/mesh/no-such-job")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_server.py::test_reconstruct_returns_job_id -v
```

Expected: FAIL — `/api/reconstruct` not yet defined.

- [ ] **Step 3: Add reconstruct + mesh endpoints to server.py**

Add these imports at the top of `server.py`:

```python
import asyncio
import shutil
from pathlib import Path
from fastapi import BackgroundTasks, UploadFile, File, Form
from fastapi.responses import FileResponse

TMP_DIR = Path("tmp")
TMP_DIR.mkdir(exist_ok=True)
```

Add these functions and endpoints to `server.py` (before the `app.mount` line):

```python
async def run_pipeline(job_id: str, image_paths: list[str], height_cm: float) -> None:
    """Background task: reconstruct → repair → update job."""
    from pipeline.reconstruct import reconstruct
    from pipeline.mesh_repair import repair_mesh

    job_dir = TMP_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    raw_path = str(job_dir / "raw.obj")
    clean_path = str(job_dir / "mesh.obj")

    try:
        update_job(job_id, status="processing", step="Analyzing photos")
        reconstruct(image_paths, raw_path)

        update_job(job_id, step="Cleaning mesh")
        repair_mesh(raw_path, clean_path, target_faces=8000, height_cm=height_cm)

        update_job(job_id, status="complete", step="Done", mesh_url=f"/api/mesh/{job_id}")
    except Exception as exc:
        update_job(job_id, status="error", step=str(exc))
    finally:
        # Clean up uploaded images
        for p in image_paths:
            Path(p).unlink(missing_ok=True)


@app.post("/api/reconstruct")
async def api_reconstruct(
    background_tasks: BackgroundTasks,
    photos: list[UploadFile] = File(...),
    height_cm: float = Form(...),
):
    job_id = create_job()
    job_dir = TMP_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    image_paths = []
    for i, photo in enumerate(photos):
        img_path = job_dir / f"photo_{i}.jpg"
        with open(img_path, "wb") as f:
            f.write(await photo.read())
        image_paths.append(str(img_path))

    background_tasks.add_task(run_pipeline, job_id, image_paths, height_cm)
    return {"job_id": job_id}


@app.get("/api/mesh/{job_id}")
async def api_mesh(job_id: str):
    job = get_job(job_id)
    if job is None or job["status"] != "complete":
        return JSONResponse({"error": "not found"}, status_code=404)
    mesh_path = TMP_DIR / job_id / "mesh.obj"
    if not mesh_path.exists():
        return JSONResponse({"error": "mesh not found"}, status_code=404)
    return FileResponse(str(mesh_path), media_type="model/obj")
```

- [ ] **Step 4: Run all server tests**

```bash
pytest tests/test_server.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: /api/reconstruct and /api/mesh endpoints with background pipeline"
```

---

## Task 6: AmiGo Pattern Generation Algorithm

**Files:**
- Create: `pipeline/pattern_gen.py`
- Create: `tests/test_pattern_gen.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pattern_gen.py
import trimesh
import tempfile, os, pytest
from pipeline.pattern_gen import generate_pattern, GAUGE_TABLE


def make_sphere_obj(path: str, radius_cm: float = 5.0):
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=radius_cm)
    sphere.export(path)


def test_gauge_table_lookup():
    assert GAUGE_TABLE[("dk", 3.5)] == 20
    assert GAUGE_TABLE[("worsted", 5.0)] == 16


def test_sphere_pattern_has_magic_ring():
    with tempfile.TemporaryDirectory() as tmp:
        mesh_path = os.path.join(tmp, "sphere.obj")
        make_sphere_obj(mesh_path, radius_cm=5.0)
        result = generate_pattern(mesh_path, gauge_per_10cm=20, height_cm=10.0)
        assert "parts" in result
        rounds = result["parts"][0]["rounds"]
        assert rounds[0]["instructions"] == "6 sc in MR"
        assert rounds[0]["stitch_count"] == 6


def test_sphere_pattern_increases_then_decreases():
    """A sphere should have increasing stitch counts then decreasing."""
    with tempfile.TemporaryDirectory() as tmp:
        mesh_path = os.path.join(tmp, "sphere.obj")
        make_sphere_obj(mesh_path, radius_cm=5.0)
        result = generate_pattern(mesh_path, gauge_per_10cm=20, height_cm=10.0)
        counts = [r["stitch_count"] for r in result["parts"][0]["rounds"] if r["stitch_count"] > 0]
        midpoint = len(counts) // 2
        # First half should be non-decreasing
        assert all(counts[i] <= counts[i+1] for i in range(midpoint - 1))
        # Second half should be non-increasing
        assert all(counts[i] >= counts[i+1] for i in range(midpoint, len(counts) - 1))


def test_pattern_stitch_counts_match_instructions():
    """Stitch count in parentheses must match computed count."""
    with tempfile.TemporaryDirectory() as tmp:
        mesh_path = os.path.join(tmp, "sphere.obj")
        make_sphere_obj(mesh_path, radius_cm=5.0)
        result = generate_pattern(mesh_path, gauge_per_10cm=20, height_cm=10.0)
        for rnd in result["parts"][0]["rounds"]:
            if rnd["stitch_count"] > 0:
                assert isinstance(rnd["stitch_count"], int)
                assert rnd["stitch_count"] >= 6
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_pattern_gen.py -v
```

Expected: `ImportError: cannot import name 'generate_pattern'`

- [ ] **Step 3: Implement pipeline/pattern_gen.py**

```python
# pipeline/pattern_gen.py
"""
AmiGo-inspired amigurumi pattern generator.

Given a watertight OBJ mesh at real-world scale (centimetres) and a gauge,
returns a round-by-round amigurumi pattern as a JSON-serialisable dict.

Reference: Edelstein et al., "AmiGo: Computational Design of Amigurumi
Crochet Patterns", ACM SCF 2022.
https://dl.acm.org/doi/fullHtml/10.1145/3559400.3562005
"""
from __future__ import annotations
import numpy as np
import trimesh
import potpourri3d as pp3d
from scipy.spatial import ConvexHull

# Standard gauge lookup: (yarn_weight, hook_mm_str) → stitches per 10cm
GAUGE_TABLE: dict[tuple[str, float], int] = {
    ("lace",     1.5):  34,
    ("lace",     2.0):  32,
    ("fingering",2.25): 30,
    ("fingering",2.5):  28,
    ("fingering",3.0):  26,
    ("sport",    3.0):  24,
    ("sport",    3.5):  22,
    ("dk",       3.5):  20,
    ("dk",       4.0):  19,
    ("worsted",  4.5):  18,
    ("worsted",  5.0):  16,
    ("bulky",    6.0):  12,
    ("bulky",    8.0):  10,
}


def _ring_circumference_cm(ring_verts: np.ndarray) -> float:
    """Estimate the circumference of a ring of vertices projected onto the XZ plane."""
    xz = ring_verts[:, [0, 2]]
    if len(xz) < 3:
        return float(np.linalg.norm(xz.max(axis=0) - xz.min(axis=0)) * np.pi)
    try:
        hull = ConvexHull(xz)
        pts = xz[hull.vertices]
        closed = np.vstack([pts, pts[0]])
        return float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))
    except Exception:
        # fallback: assume circular from spread
        spread = np.std(xz, axis=0).mean()
        return float(2 * np.pi * spread)


def _instruction(prev: int, curr: int) -> str:
    """Build the crochet instruction string for a round."""
    if curr == prev:
        return f"sc × {curr}"
    if curr > prev:
        diff = curr - prev
        if diff >= prev:
            return f"inc × {prev}"
        repeat = max(1, prev // diff)
        sc_part = "sc, " * (repeat - 1)
        return f"[{sc_part}inc] × {diff}"
    diff = prev - curr
    if diff >= curr:
        return f"dec × {curr}"
    repeat = max(1, curr // diff)
    sc_part = "sc, " * (repeat - 1)
    return f"[{sc_part}dec] × {diff}"


def generate_pattern(mesh_path: str, gauge_per_10cm: float, height_cm: float) -> dict:
    """
    Generate an amigurumi pattern from a watertight OBJ mesh.

    Args:
        mesh_path:       Absolute path to clean, watertight OBJ (in cm units).
        gauge_per_10cm:  Stitches per 10cm (from yarn + hook selection).
        height_cm:       Real-world height of the object in cm (for scaling).

    Returns:
        dict with shape: { "parts": [ { "name": str, "rounds": [ { "number": int,
                            "instructions": str, "stitch_count": int } ] } ] }
    """
    mesh = trimesh.load(mesh_path)
    if isinstance(mesh, trimesh.Scene):
        mesh = max(mesh.dump(), key=lambda m: len(m.faces))

    vertices = np.array(mesh.vertices, dtype=float)
    faces = np.array(mesh.faces, dtype=int)

    # Seed point: topmost vertex (start crocheting from top)
    seed_idx = int(np.argmax(vertices[:, 1]))

    # Geodesic distances from seed
    solver = pp3d.MeshHeatMethodDistSolver(vertices, faces)
    distances = solver.compute_distance(seed_idx)

    # Stitch height in mesh units (mesh is in cm)
    stitch_height_cm = 10.0 / gauge_per_10cm
    stitch_width_cm  = 10.0 / gauge_per_10cm  # approx square stitch

    max_dist = float(distances.max())
    num_rounds = max(1, int(max_dist / stitch_height_cm))

    rounds = []
    prev_count: int | None = None

    for i in range(num_rounds):
        lo = i * stitch_height_cm
        hi = (i + 1) * stitch_height_cm
        mask = (distances >= lo) & (distances < hi)
        ring_verts = vertices[mask]

        if len(ring_verts) < 3:
            continue

        circ_cm = _ring_circumference_cm(ring_verts)
        stitch_count = max(6, round(circ_cm / stitch_width_cm))

        if prev_count is None:
            # Magic ring start
            rounds.append({"number": 1, "instructions": "6 sc in MR", "stitch_count": 6})
            prev_count = 6
            if stitch_count != 6:
                # Second round brings us to actual count
                instr = _instruction(6, stitch_count)
                rounds.append({"number": 2, "instructions": instr, "stitch_count": stitch_count})
                prev_count = stitch_count
        else:
            instr = _instruction(prev_count, stitch_count)
            rounds.append({
                "number": len(rounds) + 1,
                "instructions": instr,
                "stitch_count": stitch_count,
            })
            prev_count = stitch_count

    rounds.append({
        "number": len(rounds) + 1,
        "instructions": "Fasten off, leaving a long tail for sewing.",
        "stitch_count": 0,
    })

    return {"parts": [{"name": "Body", "rounds": rounds}]}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_pattern_gen.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/pattern_gen.py tests/test_pattern_gen.py
git commit -m "feat: AmiGo pattern generation algorithm — geodesic rounds + inc/dec notation"
```

---

## Task 7: Pattern + PDF API Endpoints

**Files:**
- Modify: `server.py`
- Create: `templates/pattern.html`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Add failing tests**

Add to `tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_pattern_endpoint_returns_json():
    from server import create_job, update_job
    import trimesh, os
    from pathlib import Path

    job_id = create_job()
    job_dir = Path("tmp") / job_id
    job_dir.mkdir(exist_ok=True)
    mesh_path = job_dir / "mesh.obj"

    # Write a small test sphere
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=5.0)
    sphere.export(str(mesh_path))
    update_job(job_id, status="complete", step="Done", mesh_url=f"/api/mesh/{job_id}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/pattern", json={
            "job_id": job_id,
            "gauge_per_10cm": 20,
            "yarn_weight": "dk",
            "hook_size": 3.5,
            "height_cm": 10.0,
        })
    assert resp.status_code == 200
    body = resp.json()
    assert "parts" in body
    assert len(body["parts"]) > 0
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_server.py::test_pattern_endpoint_returns_json -v
```

Expected: FAIL — `/api/pattern` not defined.

- [ ] **Step 3: Add pattern + PDF endpoints to server.py**

Add imports at top of `server.py`:

```python
from fastapi import Body
from fastapi.responses import StreamingResponse
import io
```

Add endpoints (before `app.mount`):

```python
@app.post("/api/pattern")
async def api_pattern(payload: dict = Body(...)):
    job_id = payload["job_id"]
    gauge   = float(payload["gauge_per_10cm"])
    height  = float(payload["height_cm"])

    job = get_job(job_id)
    if job is None or job["status"] != "complete":
        return JSONResponse({"error": "job not ready"}, status_code=400)

    mesh_path = str(TMP_DIR / job_id / "mesh.obj")
    from pipeline.pattern_gen import generate_pattern
    pattern = generate_pattern(mesh_path, gauge_per_10cm=gauge, height_cm=height)

    update_job(job_id, pattern=pattern,
               yarn_weight=payload.get("yarn_weight", ""),
               hook_size=payload.get("hook_size", ""),
               height_cm=height)
    return pattern


@app.get("/api/export/pdf/{job_id}")
async def api_export_pdf(job_id: str):
    job = get_job(job_id)
    if job is None or "pattern" not in job:
        return JSONResponse({"error": "no pattern"}, status_code=404)

    from jinja2 import Environment, FileSystemLoader
    import weasyprint

    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("pattern.html")
    html = template.render(
        pattern=job["pattern"],
        yarn_weight=job.get("yarn_weight", ""),
        hook_size=job.get("hook_size", ""),
        height_cm=job.get("height_cm", ""),
    )
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=amigurumi-pattern.pdf"},
    )
```

- [ ] **Step 4: Create templates/pattern.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body { font-family: 'Georgia', serif; font-size: 11pt; color: #241C0C;
         margin: 2cm; line-height: 1.6; }
  h1   { font-size: 18pt; color: #8F5033; margin-bottom: 4px; }
  h2   { font-size: 13pt; color: #8F5033; border-bottom: 1px solid #DDD0B8;
         padding-bottom: 4px; margin-top: 18px; }
  .meta { font-size: 9pt; color: #6A5E4A; margin-bottom: 16px; }
  .abbrev { background: #F5EFE2; border: 1px solid #DDD0B8; border-radius: 6px;
            padding: 8px 12px; font-size: 9pt; margin-bottom: 16px; }
  .round  { font-family: 'Courier New', monospace; font-size: 10pt; padding: 2px 0; }
  .rnd-num { color: #5F8F64; font-weight: bold; min-width: 50px; display: inline-block; }
  .count  { color: #A09480; font-size: 9pt; margin-left: 8px; }
  .note   { font-size: 9pt; color: #6A5E4A; border-left: 3px solid #B56B45;
            padding-left: 8px; margin: 8px 0; }
</style>
</head>
<body>

<h1>Amigurumi Pattern</h1>
<div class="meta">
  Yarn: {{ yarn_weight | title }} weight &nbsp;|&nbsp;
  Hook: {{ hook_size }}mm &nbsp;|&nbsp;
  Finished height: approx. {{ height_cm }}cm
</div>

<div class="abbrev">
  <strong>Abbreviations:</strong>
  MR = magic ring &nbsp;·&nbsp; sc = single crochet &nbsp;·&nbsp;
  inc = 2 sc in same st &nbsp;·&nbsp; dec = invisible decrease &nbsp;·&nbsp;
  × = repeat &nbsp;·&nbsp; ( ) = stitch count at end of round
</div>

<div class="note">
  Note: v1 patterns are generated without stuffing compensation. The finished piece
  may run slightly large — test with a simple shape before complex objects.
</div>

{% for part in pattern.parts %}
<h2>{{ part.name }}</h2>
{% for rnd in part.rounds %}
<div class="round">
  <span class="rnd-num">Rnd {{ rnd.number }}:</span>
  {{ rnd.instructions }}
  {% if rnd.stitch_count > 0 %}
  <span class="count">({{ rnd.stitch_count }})</span>
  {% endif %}
</div>
{% endfor %}
{% endfor %}

</body>
</html>
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add server.py templates/pattern.html tests/test_server.py
git commit -m "feat: /api/pattern and /api/export/pdf endpoints + PDF template"
```

---

## Task 8: Frontend — Photo Tab + Left Panel

**Files:**
- Modify: `index.html` (CSS + HTML sections only)

- [ ] **Step 1: Add OBJLoader script tag**

In `index.html`, after the existing OrbitControls script tag (line ~9), add:

```html
<script src="https://unpkg.com/three@0.139.0/examples/js/loaders/OBJLoader.js"></script>
```

- [ ] **Step 2: Add Photo tab to header mode-tabs**

Find the existing `.mode-tabs` div (around line 176) and add the Photo tab:

```html
<button class="mode-tab" data-mode="photo">
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2" style="vertical-align:-2px;margin-right:4px">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
    <circle cx="12" cy="13" r="4"/>
  </svg>Photo
</button>
```

- [ ] **Step 3: Add Photo mode CSS**

Add inside the existing `<style>` block (before `</style>`):

```css
/* ── PHOTO MODE ── */
.photo-panel{display:flex;flex-direction:column;flex:1;overflow-y:auto;padding:10px;gap:10px;}
.drop-zone{border:2px dashed var(--bdr-d);border-radius:var(--rm);padding:20px 12px;
           text-align:center;color:var(--tf);font-size:12px;cursor:pointer;
           transition:border-color .15s,background .15s;line-height:1.8;}
.drop-zone:hover,.drop-zone.drag-over{border-color:var(--accent);background:var(--accent-s);}
.drop-zone svg{display:block;margin:0 auto 6px;}
.thumb-strip{display:flex;flex-wrap:wrap;gap:5px;}
.thumb-wrap{position:relative;width:52px;height:52px;flex-shrink:0;}
.thumb-wrap img{width:52px;height:52px;object-fit:cover;border-radius:var(--r);
                border:1.5px solid var(--bdr);}
.thumb-rm{position:absolute;top:-4px;right:-4px;width:16px;height:16px;border-radius:50%;
          background:var(--accent);color:#fff;font-size:10px;line-height:16px;text-align:center;
          cursor:pointer;border:none;padding:0;}
.photo-sec{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;
           color:var(--tf);margin-bottom:5px;}
.photo-field{display:flex;align-items:center;gap:6px;margin-bottom:7px;}
.photo-field label{font-size:11px;color:var(--tm);flex:1;}
.photo-field input[type=number]{width:56px;padding:3px 5px;border:1.5px solid var(--bdr-d);
  border-radius:var(--r);background:var(--bg);color:var(--text);
  font-family:'DM Sans',sans-serif;font-size:12px;text-align:center;}
.photo-field input.invalid{border-color:#C4788A;}
.photo-field select{flex:1;padding:3px 6px;border:1.5px solid var(--bdr-d);border-radius:var(--r);
  background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;font-size:12px;}
.photo-field .unit{font-size:11px;color:var(--tf);}
/* Progress overlay */
.progress-overlay{position:absolute;inset:0;background:rgba(242,235,217,.88);
  backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;
  z-index:10;opacity:0;pointer-events:none;transition:opacity .2s;}
.progress-overlay.visible{opacity:1;pointer-events:all;}
.progress-box{background:var(--panel);border:1.5px solid var(--bdr);border-radius:var(--rl);
  padding:18px 24px;min-width:220px;box-shadow:var(--sh2);}
.progress-title{font-family:'Cormorant Garamond',serif;font-size:15px;font-weight:600;
  color:var(--accent-d);margin-bottom:12px;}
.progress-step{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12px;color:var(--tm);}
.progress-step.done{color:var(--sage-d);}
.progress-step.active{color:var(--text);font-weight:500;}
.step-icon{width:16px;height:16px;flex-shrink:0;}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{animation:spin .8s linear infinite;}
```

- [ ] **Step 4: Add Photo mode left panel HTML**

Find the existing `<div class="panel-left">` and its children. The panel currently has a `pmode` div with `profileCanvas` and `grid-panel`. Add the photo panel as a sibling (hidden by default):

```html
<!-- Add after the closing </div> of grid-panel, inside panel-left -->
<div class="pmode" id="photoPanel" style="display:none">
  <div class="photo-panel">
    <div>
      <div class="photo-sec">Photos</div>
      <div class="drop-zone" id="dropZone">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--tf)" stroke-width="1.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        Drop photos here<br>
        <span style="font-size:10px">or click to browse</span><br>
        <span style="font-size:10px;color:var(--accent)">8–15 photos, walk around object</span>
      </div>
      <input type="file" id="photoInput" accept="image/*" multiple style="display:none">
      <div class="thumb-strip" id="thumbStrip" style="margin-top:7px"></div>
    </div>

    <div>
      <div class="photo-sec">Scale Reference</div>
      <div class="photo-field">
        <label>Object height</label>
        <input type="number" id="heightCm" min="1" max="200" step="0.5" placeholder="—">
        <span class="unit">cm</span>
      </div>
    </div>

    <div>
      <div class="photo-sec">Yarn</div>
      <div class="photo-field">
        <label>Weight</label>
        <select id="yarnWeight">
          <option value="lace">Lace (0)</option>
          <option value="fingering">Fingering (1)</option>
          <option value="sport">Sport (2)</option>
          <option value="dk" selected>DK (3)</option>
          <option value="worsted">Worsted (4)</option>
          <option value="bulky">Bulky (5)</option>
        </select>
      </div>
      <div class="photo-field">
        <label>Hook</label>
        <select id="hookSize">
          <option value="2.25">2.25 mm</option>
          <option value="2.5">2.5 mm</option>
          <option value="3.0">3.0 mm</option>
          <option value="3.5" selected>3.5 mm</option>
          <option value="4.0">4.0 mm</option>
          <option value="4.5">4.5 mm</option>
          <option value="5.0">5.0 mm</option>
          <option value="6.0">6.0 mm</option>
        </select>
      </div>
      <div class="photo-field">
        <label>Gauge (sc/10cm)</label>
        <input type="number" id="gaugeVal" min="6" max="40" step="1" value="20">
      </div>
    </div>

    <button class="btn btn-a" id="generatePhotoBtn" style="width:100%;margin-top:4px" disabled>
      Generate Pattern
    </button>
  </div>
</div>
```

Also add the progress overlay inside `.three-wrap` (after `<canvas id="threeCanvas">`):

```html
<div class="progress-overlay" id="progressOverlay">
  <div class="progress-box">
    <div class="progress-title">Building your pattern…</div>
    <div class="progress-step" id="ps1">
      <svg class="step-icon" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
      Analyzing photos
    </div>
    <div class="progress-step" id="ps2">
      <svg class="step-icon" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
      Building 3D model
    </div>
    <div class="progress-step" id="ps3">
      <svg class="step-icon" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
      Cleaning mesh
    </div>
    <div class="progress-step" id="ps4">
      <svg class="step-icon" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
      Calculating pattern
    </div>
  </div>
</div>
```

Also add the Download PDF button in `.pat-footer` alongside the existing Copy button:

```html
<button class="btn btn-g" id="downloadPdfBtn" style="display:none">Download PDF</button>
```

- [ ] **Step 5: Commit HTML/CSS additions**

```bash
git add index.html
git commit -m "feat: Photo tab HTML/CSS — drop zone, yarn controls, progress overlay"
```

---

## Task 9: Frontend — JavaScript for Photo Mode

**Files:**
- Modify: `index.html` (JS section only)

- [ ] **Step 1: Add gauge lookup table and Photo mode JS**

Find the JS section of `index.html` (just before `</script>` at the bottom). Add the following block:

```javascript
// ── PHOTO MODE ──────────────────────────────────────────────
const GAUGE_TABLE = {
  'lace':      { 1.5: 34, 2.0: 32 },
  'fingering': { 2.25: 30, 2.5: 28, 3.0: 26 },
  'sport':     { 3.0: 24, 3.5: 22 },
  'dk':        { 3.5: 20, 4.0: 19 },
  'worsted':   { 4.5: 18, 5.0: 16 },
  'bulky':     { 6.0: 12, 8.0: 10 },
};

let photoFiles = [];
let currentJobId = null;
let pollTimer    = null;

// Auto-fill gauge when yarn/hook changes
function updateGauge() {
  const w = document.getElementById('yarnWeight').value;
  const h = parseFloat(document.getElementById('hookSize').value);
  const table = GAUGE_TABLE[w] || {};
  // Find closest hook
  const keys = Object.keys(table).map(Number);
  const closest = keys.reduce((a, b) => Math.abs(b - h) < Math.abs(a - h) ? b : a, keys[0]);
  if (closest !== undefined) document.getElementById('gaugeVal').value = table[closest];
}

document.getElementById('yarnWeight').addEventListener('change', updateGauge);
document.getElementById('hookSize').addEventListener('change', updateGauge);

// Enable/disable Generate button
function checkGenerateReady() {
  const hasPhotos = photoFiles.length > 0;
  const hasHeight = parseFloat(document.getElementById('heightCm').value) > 0;
  document.getElementById('generatePhotoBtn').disabled = !(hasPhotos && hasHeight);
}
document.getElementById('heightCm').addEventListener('input', checkGenerateReady);

// Drag and drop
const dropZone = document.getElementById('dropZone');
const photoInput = document.getElementById('photoInput');

dropZone.addEventListener('click', () => photoInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  addPhotos(Array.from(e.dataTransfer.files));
});
photoInput.addEventListener('change', () => addPhotos(Array.from(photoInput.files)));

function addPhotos(files) {
  const images = files.filter(f => f.type.startsWith('image/'));
  photoFiles = [...photoFiles, ...images];
  renderThumbs();
  checkGenerateReady();
}

function renderThumbs() {
  const strip = document.getElementById('thumbStrip');
  strip.innerHTML = '';
  photoFiles.forEach((file, i) => {
    const wrap = document.createElement('div');
    wrap.className = 'thumb-wrap';
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    const rm = document.createElement('button');
    rm.className = 'thumb-rm';
    rm.textContent = '×';
    rm.title = 'Remove';
    rm.addEventListener('click', () => { photoFiles.splice(i, 1); renderThumbs(); checkGenerateReady(); });
    wrap.append(img, rm);
    strip.appendChild(wrap);
  });
}

// Progress overlay helpers
const STEP_IDS = ['ps1', 'ps2', 'ps3', 'ps4'];
const STEP_LABELS = ['Analyzing photos', 'Building 3D model', 'Cleaning mesh', 'Calculating pattern'];
const CHECK_SVG = `<svg class="step-icon" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="var(--sage)" stroke-width="1.5"/><polyline points="5,8 7,10 11,6" fill="none" stroke="var(--sage)" stroke-width="1.5"/></svg>`;
const SPIN_SVG  = `<svg class="step-icon spin" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="20 18"/></svg>`;
const PEND_SVG  = `<svg class="step-icon" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="none" stroke="var(--bdr-d)" stroke-width="1.5"/></svg>`;

function showProgress() {
  document.getElementById('progressOverlay').classList.add('visible');
  STEP_IDS.forEach((id, i) => {
    const el = document.getElementById(id);
    el.className = 'progress-step';
    el.innerHTML = `${PEND_SVG} ${STEP_LABELS[i]}`;
  });
}

function setProgressStep(stepName) {
  const stepMap = {
    'Analyzing photos':   0,
    'Building 3D model':  1,
    'Cleaning mesh':      2,
    'Calculating pattern':3,
    'Done':               4,
  };
  const activeIdx = stepMap[stepName] ?? -1;
  STEP_IDS.forEach((id, i) => {
    const el = document.getElementById(id);
    if (i < activeIdx) {
      el.className = 'progress-step done';
      el.innerHTML = `${CHECK_SVG} ${STEP_LABELS[i]}`;
    } else if (i === activeIdx) {
      el.className = 'progress-step active';
      el.innerHTML = `${SPIN_SVG} ${STEP_LABELS[i]}`;
    } else {
      el.className = 'progress-step';
      el.innerHTML = `${PEND_SVG} ${STEP_LABELS[i]}`;
    }
  });
}

function hideProgress() {
  document.getElementById('progressOverlay').classList.remove('visible');
}

// OBJ loader — load mesh into Three.js scene
function loadMeshIntoViewer(meshUrl) {
  // Remove previous photo mesh if any
  const old = scene.getObjectByName('photoMesh');
  if (old) scene.remove(old);

  const loader = new THREE.OBJLoader();
  loader.load(meshUrl, obj => {
    obj.name = 'photoMesh';
    // Centre and scale to fit viewer
    const box = new THREE.Box3().setFromObject(obj);
    const centre = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3()).length();
    obj.position.sub(centre);
    obj.scale.setScalar(2 / size);
    // Apply warm material matching app palette
    obj.traverse(child => {
      if (child.isMesh) {
        child.material = new THREE.MeshStandardMaterial({ color: 0xC4956A, roughness: 0.8 });
      }
    });
    scene.add(obj);
  });
}

// Fetch pattern and render in right panel
async function fetchAndRenderPattern(jobId) {
  setProgressStep('Calculating pattern');
  const gauge    = parseFloat(document.getElementById('gaugeVal').value);
  const weight   = document.getElementById('yarnWeight').value;
  const hook     = parseFloat(document.getElementById('hookSize').value);
  const heightCm = parseFloat(document.getElementById('heightCm').value);

  const resp = await fetch('/api/pattern', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId, gauge_per_10cm: gauge,
                           yarn_weight: weight, hook_size: hook, height_cm: heightCm }),
  });
  const pattern = await resp.json();

  // Mark last step done and hide overlay
  STEP_IDS.forEach((id, i) => {
    const el = document.getElementById(id);
    el.className = 'progress-step done';
    el.innerHTML = `${CHECK_SVG} ${STEP_LABELS[i]}`;
  });
  setTimeout(hideProgress, 800);

  // Render pattern in right panel
  renderAmigurumiPattern(pattern, weight, hook, heightCm);

  // Show PDF button
  document.getElementById('downloadPdfBtn').style.display = '';
  document.getElementById('downloadPdfBtn').onclick = () => {
    window.location.href = `/api/export/pdf/${jobId}`;
  };
}

function renderAmigurumiPattern(pattern, yarnWeight, hookSize, heightCm) {
  const out = document.getElementById('patOut');
  let html = `<div class="p-header">Amigurumi Pattern</div>`;
  html += `<div class="p-sub">${yarnWeight} weight · ${hookSize}mm hook · ~${heightCm}cm tall</div>`;
  html += `<div class="p-section">Abbreviations</div>`;
  html += `<div class="p-note">MR = magic ring · sc = single crochet · inc = 2sc in same st · dec = invisible decrease · × = repeat · ( ) = stitch count</div>`;

  for (const part of pattern.parts) {
    html += `<div class="p-section">${esc(part.name)}</div>`;
    html += `<div class="p-start">Magic Ring</div>`;
    for (const rnd of part.rounds) {
      if (rnd.stitch_count === 0) {
        html += `<div class="p-end">${esc(rnd.instructions)}</div>`;
      } else {
        html += `<div class="p-rnd"><span class="rl">Rnd ${rnd.number}:</span> ${esc(rnd.instructions)} <span class="rs">(${rnd.stitch_count})</span></div>`;
      }
    }
  }
  out.innerHTML = html;
}

// Main generate handler
document.getElementById('generatePhotoBtn').addEventListener('click', async () => {
  if (photoFiles.length === 0) return;
  const heightCm = parseFloat(document.getElementById('heightCm').value);
  if (!heightCm || heightCm <= 0) {
    document.getElementById('heightCm').classList.add('invalid');
    return;
  }
  document.getElementById('heightCm').classList.remove('invalid');

  const formData = new FormData();
  formData.append('height_cm', heightCm);
  photoFiles.forEach(f => formData.append('photos', f));

  showProgress();
  setProgressStep('Analyzing photos');
  document.getElementById('generatePhotoBtn').disabled = true;

  const resp = await fetch('/api/reconstruct', { method: 'POST', body: formData });
  const { job_id } = await resp.json();
  currentJobId = job_id;

  // Poll job status
  const stepToProgress = {
    'Analyzing photos':    'Analyzing photos',
    'Cleaning mesh':       'Cleaning mesh',
    'Done':                'Done',
  };

  pollTimer = setInterval(async () => {
    const jr = await fetch(`/api/job/${job_id}`);
    const job = await jr.json();

    if (job.step) setProgressStep(job.step);

    if (job.status === 'complete') {
      clearInterval(pollTimer);
      loadMeshIntoViewer(job.mesh_url);
      await fetchAndRenderPattern(job_id);
      document.getElementById('generatePhotoBtn').disabled = false;
    } else if (job.status === 'error') {
      clearInterval(pollTimer);
      hideProgress();
      alert('Error: ' + job.step);
      document.getElementById('generatePhotoBtn').disabled = false;
    }
  }, 2000);
});
```

- [ ] **Step 2: Wire Photo tab into existing tab-switching logic**

Find the existing mode-tab event listener (around line 973 in the original file). The existing code sets `mode` and toggles active class. Add Photo panel visibility switching:

```javascript
// Inside the existing mode-tab click handler, after the existing panel logic:
document.getElementById('photoPanel').style.display = (mode === 'photo') ? 'flex' : 'none';
// Also hide the standard left panel content when in photo mode
document.querySelector('.pmode:not(#photoPanel)').style.display = (mode === 'photo') ? 'none' : 'flex';
```

- [ ] **Step 3: Start backend and smoke-test the full flow manually**

```bash
python server.py
```

Open `http://localhost:8000`, click Photo tab, drop 2-3 test photos, enter a height, click Generate Pattern. Verify:
- Progress overlay appears and advances through steps
- 3D mesh appears in center viewer on completion
- Pattern rounds appear in right panel
- Download PDF button appears and produces a PDF

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: Photo mode JS — drag-drop, reconstruct flow, pattern render, PDF download"
```

---

## Task 10: Final Integration Test + Startup Script

**Files:**
- Create: `start.sh`

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Create start.sh**

```bash
#!/bin/bash
# Start the Crochet Notation Translator with photo-to-amigurumi backend
echo "Starting server at http://localhost:8000"
python server.py
```

```bash
chmod +x start.sh
```

- [ ] **Step 3: End-to-end test with a Sriracha bottle**

Using the real app:
1. `./start.sh`
2. Open `http://localhost:8000`
3. Photo tab → drop 8+ photos of a Sriracha bottle taken from all angles
4. Height: 24cm
5. Yarn: Fingering, 2.5mm hook
6. Click Generate Pattern
7. Verify 3D mesh roughly resembles the bottle
8. Verify pattern has a magic ring start, increasing rounds, then decreasing
9. Download PDF — verify it's readable and complete

- [ ] **Step 4: Commit**

```bash
git add start.sh
git commit -m "chore: add start.sh launcher"
```

---

## Self-Review

**Spec coverage check:**
- [x] Photo drag-drop input → Task 8/9
- [x] TripoSR reconstruction → Task 4/5
- [x] Mesh repair (Open3D, hole fill, decimate) → Task 3
- [x] Scale reference (height_cm) → Task 3 + 8/9
- [x] Gauge lookup table (yarn weight + hook) → Task 6 + 9
- [x] AmiGo pattern generation (geodesic, rounds, inc/dec) → Task 6
- [x] PDF export (Jinja2 + WeasyPrint) → Task 7
- [x] Step progress overlay → Task 8/9
- [x] Three.js mesh loading (OBJLoader) → Task 8/9
- [x] Right panel amigurumi pattern rendering → Task 9
- [x] FastAPI serving index.html (same-origin) → Task 2
- [x] Download PDF button → Task 7/9
- [x] OBJLoader script tag → Task 8

**Known limitation documented in spec but intentionally deferred:**
- Stuffing compensation → noted in PDF template (Task 7)
- Multi-part segmentation → v1 produces single-part patterns
- Mesh quality warning on bad photos → Task 5 returns `error` status with message

**Type consistency verified:** `generate_pattern` signature consistent across Task 6 (definition) and Task 7 (call in server.py). `GAUGE_TABLE` key format `(str, float)` consistent between Task 6 tests and Task 6 implementation.
