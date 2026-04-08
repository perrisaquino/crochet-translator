import uuid
from threading import Lock
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

app = FastAPI()
_jobs: dict[str, dict] = {}
_jobs_lock = Lock()


def create_job() -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"status": "pending", "step": None, "mesh_url": None}
    return job_id


def update_job(job_id: str, **kwargs) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
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
