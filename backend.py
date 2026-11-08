import os
import time
import json
import uuid
import subprocess
import requests
from pathlib import Path


POLLO_URL = "https://pollo.ai/api/platform/v1/generation/pollo-ai/pollo-v2/video"


def make_prompt(scene, characters, language):
    char_text = "\n".join(
        [
            f"- {c['name']}: {c['role']}. Appearance: {c['look']}"
            for c in characters
        ]
    )

    return f"""
Create a high-quality 3D animated cartoon scene.

VISUAL STYLE:
Modern family-friendly 3D cartoon animation,
colorful Indian village environment,
smooth character animation,
expressive faces,
cinematic lighting,
soft realistic shadows,
detailed 3D models,
clean polished animation,
fun YouTube cartoon style.

CHARACTERS:
{char_text}

SCENE:
{scene}

ACTION:
Animate the characters naturally.
Keep the characters visually consistent with the descriptions.
Use believable body movement, facial expressions and camera movement.

CAMERA:
Cinematic medium shot, occasional gentle camera movement,
clear subject framing, smooth motion.

IMPORTANT:
No text on screen.
No subtitles inside the generated video.
No watermark.
No horror.
No violence.
Family friendly.

Language/context: {language}
"""


def submit_pollo(prompt, api_key, aspect_ratio="16:9"):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }

    payload = {
        "input": {
            "prompt": prompt,
            "resolution": "480p",
            "duration": 10,
            "aspectRatio": aspect_ratio,
            "generateAudio": False
        }
    }

    r = requests.post(
        POLLO_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    r.raise_for_status()

    data = r.json()

    task_id = data.get("taskId")

    if not task_id:
        raise RuntimeError(f"Pollo task ID नहीं मिला: {data}")

    return task_id


def check_pollo(task_id, api_key):
    url = f"https://pollo.ai/api/platform/v1/generation/{task_id}/status"

    headers = {
        "x-api-key": api_key
    }

    r = requests.get(
        url,
        headers=headers,
        timeout=60
    )

    r.raise_for_status()

    return r.json()


def wait_for_video(task_id, api_key, timeout=900):
    start = time.time()

    while True:

        data = check_pollo(task_id, api_key)

        generations = data.get("generations", [])

        if generations:

            g = generations[0]

            status = g.get("status")

            if status == "succeeded":

                video_url = g.get("url")

                if video_url:
                    return video_url

            if status in ["failed", "error"]:
                raise RuntimeError(
                    g.get("failMsg") or "Pollo video generation failed"
                )

        if time.time() - start > timeout:
            raise TimeoutError("Video generation timeout")

        time.sleep(8)


def download_video(url, output):
    r = requests.get(
        url,
        stream=True,
        timeout=300
    )

    r.raise_for_status()

    with open(output, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)


def concat_videos(video_files, final_file):

    list_file = Path(final_file).parent / "videos.txt"

    with open(list_file, "w", encoding="utf-8") as f:

        for video in video_files:
            safe_path = str(Path(video).resolve()).replace("'", "'\\''")

            f.write(
                f"file '{safe_path}'\n"
            )

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(final_file)
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:

        raise RuntimeError(
            "FFmpeg error:\n" + result.stderr[-4000:]
        )

    return final_file


def render_job(job, api_key, progress_callback=None):

    job_id = job["id"]

    work = Path("data") / "renders" / job_id
    work.mkdir(parents=True, exist_ok=True)

    scenes = job["scenes"]
    characters = job["characters"]
    language = job["language"]

    aspect_ratio = (
        "16:9"
        if job["format"].startswith("16")
        else "9:16"
    )

    video_files = []

    total = len(scenes)

    for index, scene in enumerate(scenes):

        output = work / f"scene_{index + 1:03d}.mp4"

        if output.exists():
            video_files.append(str(output))
            continue

        prompt = make_prompt(
            scene["prompt"],
            characters,
            language
        )

        if progress_callback:
            progress_callback(
                index + 1,
                total,
                f"AI scene {index + 1}/{total} generate हो रहा है..."
            )

        task_id = submit_pollo(
            prompt,
            api_key,
            aspect_ratio
        )

        video_url = wait_for_video(
            task_id,
            api_key
        )

        download_video(
            video_url,
            output
        )

        video_files.append(str(output))

    final_file = work / f"CartoonFlow_{job_id}.mp4"

    concat_videos(
        video_files,
        final_file
    )

    return str(final_file)
