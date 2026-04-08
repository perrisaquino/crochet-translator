import asyncio
import uuid
from pathlib import Path
from threading import Lock
from fastapi import BackgroundTasks, Body, FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import io as _io

BASE_DIR = Path(__file__).parent
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)

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

    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")))
    template = env.get_template("pattern.html")
    html = template.render(
        pattern=job["pattern"],
        yarn_weight=job.get("yarn_weight", ""),
        hook_size=job.get("hook_size", ""),
        height_cm=job.get("height_cm", ""),
    )
    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        _io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=amigurumi-pattern.pdf"},
    )


# Serve index.html and static assets — must be LAST
app.mount("/", StaticFiles(directory=str(BASE_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
