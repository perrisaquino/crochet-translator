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
