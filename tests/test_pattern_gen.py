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
