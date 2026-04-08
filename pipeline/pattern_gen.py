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

# Standard gauge lookup: (yarn_weight, hook_mm) → stitches per 10cm
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


def _ring_circumference(ring_verts: np.ndarray) -> float:
    """Estimate circumference of a ring of vertices projected onto the XZ plane."""
    xz = ring_verts[:, [0, 2]]
    if len(xz) < 3:
        return float(np.linalg.norm(xz.max(axis=0) - xz.min(axis=0)) * np.pi)
    try:
        hull = ConvexHull(xz)
        pts = xz[hull.vertices]
        closed = np.vstack([pts, pts[0]])
        return float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))
    except Exception:
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
    # decreasing
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
        mesh_path:       Absolute path to clean, watertight OBJ.
        gauge_per_10cm:  Stitches per 10cm (from yarn + hook selection).
        height_cm:       Real-world height of the object in cm (for scale).

    Returns:
        dict with shape: {
            "parts": [ {
                "name": str,
                "rounds": [ {"number": int, "instructions": str, "stitch_count": int} ]
            } ]
        }
    """
    mesh = trimesh.load(mesh_path)
    if isinstance(mesh, trimesh.Scene):
        mesh = max(mesh.dump(), key=lambda m: len(m.faces))

    vertices = np.array(mesh.vertices, dtype=float)
    faces = np.array(mesh.faces, dtype=int)

    # Scale mesh so its largest extent equals height_cm
    current_extent = mesh.extents.max()
    if current_extent > 0 and height_cm > 0:
        scale = height_cm / current_extent
        vertices = vertices * scale

    # Seed point: topmost vertex
    seed_idx = int(np.argmax(vertices[:, 1]))

    # Geodesic distances from seed using Heat Method
    solver = pp3d.MeshHeatMethodDistanceSolver(vertices, faces)
    distances = solver.compute_distance(seed_idx)

    # Stitch height in same units as scaled vertices (cm)
    stitch_height = 10.0 / gauge_per_10cm
    stitch_width  = 10.0 / gauge_per_10cm

    max_dist = float(distances[np.isfinite(distances)].max())
    num_rounds = max(1, int(max_dist / stitch_height))

    rounds = []
    prev_count: int | None = None

    for i in range(min(num_rounds, 120)):  # cap at 120 rounds
        lo = i * stitch_height
        hi = (i + 1) * stitch_height
        mask = (distances >= lo) & (distances < hi)
        ring_verts = vertices[mask]

        if len(ring_verts) < 3:
            continue

        circ = _ring_circumference(ring_verts)
        stitch_count = max(6, round(circ / stitch_width))

        if prev_count is None:
            rounds.append({"number": 1, "instructions": "6 sc in MR", "stitch_count": 6})
            prev_count = 6
            if stitch_count != 6:
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
