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
