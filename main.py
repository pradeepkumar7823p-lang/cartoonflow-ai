    import os
import uuid
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="CartoonFlow AI")

BASE = Path("/tmp/cartoonflow")
BASE.mkdir(parents=True, exist_ok=True)


class VideoRequest(BaseModel):
    story: str
    language: str = "Hindi"
    aspect_ratio: str = "16:9"
    duration_minutes: int = 4


@app.get("/")
def home():
    return {
        "name": "CartoonFlow AI",
        "status": "online",
        "message": "CartoonFlow AI backend is running"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
def generate_video(req: VideoRequest):

    if not req.story.strip():
        raise HTTPException(status_code=400, detail="Story is required")

    job_id = uuid.uuid4().hex[:8]

    job_dir = BASE / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Scene count:
    # 3 minutes = 30 scenes
    # 4 minutes = 40 scenes
    scenes = req.duration_minutes * 10

    manifest = {
        "job_id": job_id,
        "story": req.story,
        "language": req.language,
        "aspect_ratio": req.aspect_ratio,
        "duration_minutes": req.duration_minutes,
        "scene_count": scenes,
        "status": "queued"
    }

    import json

    with open(job_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest


@app.get("/job/{job_id}")
def get_job(job_id: str):

    manifest = BASE / job_id / "manifest.json"

    if not manifest.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    import json

    with open(manifest, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/download/{job_id}")
def download_video(job_id: str):

    video = BASE / job_id / "final.mp4"

    if not video.exists():
        raise HTTPException(
            status_code=404,
            detail="Video is not ready yet"
        )

    return FileResponse(
        video,
        media_type="video/mp4",
        filename=f"cartoonflow-{job_id}.mp4"
    )
