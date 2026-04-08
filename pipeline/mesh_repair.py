import os
import tempfile
from collections import defaultdict

import numpy as np
import trimesh


def _fill_holes_fan(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Fill open boundary loops using fan triangulation from each loop's centroid.
    Handles multiple independent holes. Returns a new mesh.
    """
    verts = list(mesh.vertices)
    faces = list(mesh.faces)

    edge_counts: dict[tuple, int] = defaultdict(int)
    for f in faces:
        for i in range(3):
            e = tuple(sorted((int(f[i]), int(f[(i + 1) % 3]))))
            edge_counts[e] += 1

    boundary_edges = [e for e, c in edge_counts.items() if c == 1]
    if not boundary_edges:
        return mesh

    adj: dict[int, list[int]] = defaultdict(list)
    for a, b in boundary_edges:
        adj[a].append(b)
        adj[b].append(a)

    visited: set[int] = set()
    new_faces: list[list[int]] = []

    for start_edge in boundary_edges:
        start = start_edge[0]
        if start in visited:
            continue

        loop = [start]
        visited.add(start)
        prev = None
        curr = start

        while True:
            neighbors = [n for n in adj[curr] if n != prev and n not in visited]
            if not neighbors:
                break
            nxt = neighbors[0]
            visited.add(nxt)
            loop.append(nxt)
            prev = curr
            curr = nxt

        if len(loop) < 3:
            continue

        centroid = np.mean([verts[i] for i in loop], axis=0)
        centroid_idx = len(verts)
        verts.append(centroid)

        for i in range(len(loop)):
            a = loop[i]
            b = loop[(i + 1) % len(loop)]
            new_faces.append([a, b, centroid_idx])

    if not new_faces:
        return mesh

    return trimesh.Trimesh(
        vertices=np.array(verts),
        faces=np.vstack([faces, new_faces]),
        process=True,
    )


def repair_mesh(src_path: str, dst_path: str, target_faces: int = 8000, height_cm: float | None = None) -> None:
    """
    Load a mesh, fill holes, decimate, optionally scale to real-world height, save.

    Args:
        src_path:     Input OBJ path (may be noisy/open).
        dst_path:     Output OBJ path (watertight, decimated).
        target_faces: Target face count after decimation (default 8000).
        height_cm:    If provided, uniformly scale mesh so its Y-axis height equals this value in cm.
    """
    mesh = trimesh.load(src_path, force="mesh")

    # Ensure single mesh (take largest if scene)
    if isinstance(mesh, trimesh.Scene):
        mesh = max(mesh.dump(), key=lambda m: len(m.faces))

    # Fill holes if not already watertight
    if not mesh.is_watertight:
        mesh = _fill_holes_fan(mesh)

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
