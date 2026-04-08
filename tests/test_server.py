import io
import pytest
from unittest.mock import patch
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
