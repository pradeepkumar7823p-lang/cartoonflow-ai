import os, json, uuid, asyncio, subprocess, shutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import fal_client
import edge_tts

load_dotenv()
BASE = Path(__file__).parent
DATA = BASE / "data"
OUT = DATA / "outputs"
DATA.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

app = FastAPI(title="CartoonFlow AI")
app.mount("/static", StaticFiles(directory=BASE/"static"), name="static")

VIDEO_MODEL = os.getenv("VIDEO_MODEL", "fal-ai/kling-video/o3/4k/image-to-video")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "fal-ai/gpt-image-1.5")

def ensure_key():
    if not os.getenv("FAL_KEY"):
        raise HTTPException(500, "FAL_KEY server environment variable is missing.")

def scene_prompts(story, lang, minutes):
    # 6 seconds per scene. This is intentionally simple and deterministic.
    count = max(10, int(minutes * 10))
    base = f"""Create a high-quality 3D animated cartoon scene for a family-friendly YouTube video.
Story: {story}
Language: {lang}
Keep the main characters visually consistent: same face, hairstyle, clothes, colors and proportions in every scene.
Use cinematic 3D animation, expressive faces, natural lighting, clean composition, no text, no watermark."""
    prompts = []
    for i in range(count):
        prompts.append({
            "scene": i+1,
            "image_prompt": base + f"\nScene {i+1} of {count}: advance the story naturally. Show a clear action and emotion.",
            "motion_prompt": "Smooth cinematic 3D cartoon animation, natural body movement, expressive facial reaction, gentle camera motion, no text."
        })
    return prompts

def call_fal(endpoint, arguments):
    ensure_key()
    return fal_client.subscribe(endpoint, arguments=arguments)

def extract_url(result):
    # Handles common fal result shapes.
    if isinstance(result, dict):
        if result.get("video", {}).get("url"):
            return result["video"]["url"]
        if result.get("image", {}).get("url"):
            return result["image"]["url"]
        for v in result.values():
            if isinstance(v, dict):
                u = extract_url(v)
                if u: return u
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        u = extract_url(item)
                        if u: return u
    return None

async def download(url, path):
    import httpx
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.get(url)
        r.raise_for_status()
        path.write_bytes(r.content)

async def tts(text, path, lang):
    voice = "hi-IN-SwaraNeural" if lang.lower().startswith("h") else "en-US-JennyNeural"
    await edge_tts.Communicate(text, voice).save(str(path))

async def make_video(job_id, story, lang, minutes, fmt):
    work = DATA / job_id
    work.mkdir(parents=True, exist_ok=True)
    scenes = scene_prompts(story, lang, minutes)
    manifest = work / "manifest.json"
    manifest.write_text(json.dumps({"job_id":job_id,"story":story,"language":lang,"format":fmt,"scenes":scenes}, ensure_ascii=False, indent=2), encoding="utf-8")

    clips=[]
    for s in scenes:
        img_res = call_fal(IMAGE_MODEL, {
            "prompt": s["image_prompt"],
            "aspect_ratio": "landscape_16_9" if fmt == "16:9" else "portrait_16_9"
        })
        img_url = extract_url(img_res)
        if not img_url:
            raise RuntimeError(f"Scene {s['scene']}: image URL not returned")
        img = work / f"{s['scene']:03d}.png"
        await download(img_url, img)

        vid_res = call_fal(VIDEO_MODEL, {
            "image_url": img_url,
            "prompt": s["motion_prompt"],
            "duration": "5"
        })
        vid_url = extract_url(vid_res)
        if not vid_url:
            raise RuntimeError(f"Scene {s['scene']}: video URL not returned")
        clip = work / f"{s['scene']:03d}.mp4"
        await download(vid_url, clip)
        clips.append(clip)

    # TTS narration. For a production system, the story should be split into scene narration.
    audio = work / "narration.mp3"
    await tts(story, audio, lang)

    concat = work / "concat.txt"
    concat.write_text("\n".join(f"file '{p.resolve()}'" for p in clips), encoding="utf-8")
    silent = work / "silent.mp4"
    final = OUT / f"{job_id}.mp4"

    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-c","copy",str(silent)], check=True)
    # Scale/crop to requested output. Audio is looped/truncated to video duration.
    if fmt == "9:16":
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:
        vf = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
    subprocess.run([
        "ffmpeg","-y","-i",str(silent),"-i",str(audio),
        "-map","0:v:0","-map","1:a:0","-vf",vf,
        "-c:v","libx264","-preset","veryfast","-crf","23",
        "-c:a","aac","-shortest",str(final)
    ], check=True)
    return final

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse((BASE/"static"/"index.html").read_text(encoding="utf-8"))

@app.post("/api/render")
async def render(
    story: str = Form(...),
    language: str = Form("Hindi"),
    minutes: int = Form(1),
    fmt: str = Form("16:9")
):
    if not story.strip():
        raise HTTPException(400, "Story is required")
    if minutes < 1 or minutes > 4:
        raise HTTPException(400, "Minutes must be 1-4")
    job_id = uuid.uuid4().hex[:8]
    asyncio.create_task(run_job(job_id, story, language, minutes, fmt))
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/status/{job_id}")
async def status(job_id: str):
    p = DATA / job_id / "status.json"
    if not p.exists():
        return {"job_id":job_id,"status":"queued"}
    return JSONResponse(json.loads(p.read_text()))

@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    p = OUT / f"{job_id}.mp4"
    if not p.exists():
        raise HTTPException(404, "Video not ready")
    return FileResponse(p, media_type="video/mp4", filename=f"CartoonFlow_{job_id}.mp4")

async def run_job(job_id, story, language, minutes, fmt):
    p = DATA / job_id
    p.mkdir(exist_ok=True)
    def write(status, message=""):
        (p/"status.json").write_text(json.dumps({"job_id":job_id,"status":status,"message":message}, ensure_ascii=False), encoding="utf-8")
    try:
        write("generating","Generating scene images and video clips...")
        await make_video(job_id, story, language, minutes, fmt)
        write("complete","Video ready")
    except Exception as e:
        write("failed",str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
