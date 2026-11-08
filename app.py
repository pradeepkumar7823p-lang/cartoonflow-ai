import streamlit as st
from pathlib import Path
import json, os, re, uuid, datetime, time, subprocess, shutil
import requests

BASE = Path(__file__).parent
DATA = BASE / "data"
OUTPUT = BASE / "output"
DATA.mkdir(exist_ok=True)
OUTPUT.mkdir(exist_ok=True)
JOBS = DATA / "jobs.json"
if not JOBS.exists():
    JOBS.write_text("[]", encoding="utf-8")

st.set_page_config(page_title="CartoonFlow AI", page_icon="🎬", layout="wide")

def load_jobs():
    try:
        return json.loads(JOBS.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_jobs(jobs):
    JOBS.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")

def scene_plan(story, chars, minutes):
    # 10-second AI clips. 3 min = 18 clips, 4 min = 24 clips.
    n = int(minutes * 6)
    parts = [x.strip() for x in re.split(r"(?<=[.!?।])\s+|\n+", story) if x.strip()]
    if not parts:
        parts = ["कहानी शुरू होती है।", "हीरो एक मजेदार काम करता है।",
                 "अचानक समस्या आती है।", "हीरो समस्या हल करता है।",
                 "कहानी खुशहाल अंत के साथ खत्म होती है।"]
    char_text = "; ".join(f"{c['name']}: {c['look']}" for c in chars)
    out = []
    for i in range(n):
        line = parts[i % len(parts)]
        out.append({
            "scene": i + 1,
            "duration": 10,
            "prompt": (
                "High-quality stylized 3D cartoon animation for a family-friendly YouTube story. "
                "Keep the same characters, faces, clothes, body proportions and colors throughout. "
                f"CHARACTERS: {char_text}. ACTION: {line} "
                "Indian village environment, colorful 3D animated-film look, expressive faces, "
                "smooth natural character motion, cinematic camera movement, good lighting, "
                "clean composition, no captions, no text, no watermark."
            )
        })
    return out

def make_job(story, chars, lang, fmt, minutes):
    return {
        "id": str(uuid.uuid4())[:8],
        "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Queued",
        "language": lang,
        "format": "16:9" if fmt.startswith("16") else "9:16",
        "minutes": int(minutes),
        "story": story,
        "characters": chars,
        "scenes": scene_plan(story, chars, minutes),
        "output": None,
        "error": None,
    }

def ffmpeg_path():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

def pollo_headers(api_key):
    return {"Content-Type": "application/json", "x-api-key": api_key}

def pollo_video(api_key, prompt, aspect_ratio):
    url = "https://pollo.ai/api/platform/v1/generation/pollo-ai/pollo-v2/video"
    payload = {
        "input": {
            "prompt": prompt,
            "resolution": "480p",
            "duration": 10,
            "aspectRatio": aspect_ratio,
            "generateAudio": True
        }
    }
    r = requests.post(url, headers=pollo_headers(api_key), json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Pollo submit error {r.status_code}: {r.text[:1500]}")
    data = r.json()
    task_id = data.get("taskId")
    if not task_id:
        raise RuntimeError(f"Pollo ने taskId नहीं दिया: {data}")
    return task_id

def pollo_wait(api_key, task_id, timeout_seconds=900):
    url = f"https://pollo.ai/api/platform/v1/generation/{task_id}/status"
    start = time.time()
    while time.time() - start < timeout_seconds:
        r = requests.get(url, headers={"x-api-key": api_key}, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Pollo status error {r.status_code}: {r.text[:1200]}")
        data = r.json()
        generations = data.get("generations") or []
        if generations:
            g = generations[0]
            status = str(g.get("status", "")).lower()
            if status in ("succeeded", "success", "completed", "complete"):
                video_url = g.get("url")
                if video_url:
                    return video_url
                raise RuntimeError(f"Generation complete लेकिन video URL नहीं मिला: {data}")
            if status in ("failed", "error"):
                raise RuntimeError(g.get("failMsg") or str(data))
        time.sleep(8)
    raise TimeoutError("Pollo job timeout: 15 मिनट से ज्यादा हो गए।")

def download(url, path):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

def concat_videos(files, output):
    ff = ffmpeg_path()
    if not ff:
        raise RuntimeError("FFmpeg उपलब्ध नहीं है। requirements.txt में imageio-ffmpeg रखें।")
    list_file = output.parent / f"{output.stem}_list.txt"
    with list_file.open("w", encoding="utf-8") as f:
        for p in files:
            f.write(f"file '{p.resolve().as_posix()}'\n")
    cmd = [
        ff, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", "-movflags", "+faststart", str(output)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)
    if result.returncode != 0:
        # fallback: re-encode for mismatched clip parameters
        cmd2 = [
            ff, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(output)
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True)
        if result2.returncode != 0:
            raise RuntimeError(result2.stderr[-2500:])
    return output

st.title("🎬 CartoonFlow AI")
st.caption("Android-first AI 3D cartoon video generator")

with st.sidebar:
    st.header("Project")
    lang = st.selectbox("Language", ["Hindi", "English", "Hinglish"])
    fmt = st.selectbox("Format", ["16:9 YouTube", "9:16 Shorts"])
    minutes = st.slider("Video length", 3, 4, 4)

    st.divider()
    st.header("Characters")
    count = st.number_input("Characters", 1, 6, 2, 1)
    defaults = [
        ("Golu", "Hero", "7-year-old Indian boy, round friendly face, black hair, yellow T-shirt, blue shorts, red shoes"),
        ("Motu", "Friend", "cute gray elephant, big expressive eyes, blue scarf, friendly smile"),
    ]
    chars = []
    for i in range(int(count)):
        d = defaults[i] if i < len(defaults) else (f"Character {i+1}", "Supporting", "friendly 3D cartoon character")
        with st.expander(d[0], expanded=i < 2):
            name = st.text_input("Name", d[0], key=f"name_{i}")
            role = st.text_input("Role", d[1], key=f"role_{i}")
            look = st.text_area("Fixed appearance", d[2], key=f"look_{i}", height=90)
            chars.append({"name": name, "role": role, "look": look})

st.subheader("📜 कहानी")
story = st.text_area(
    "Story",
    value=("गोलू और मोटू गाँव में जंगल की ओर जाते हैं। "
           "रास्ते में उन्हें एक चमकता हुआ आम मिलता है। "
           "दोनों आम को लेकर मजेदार परेशानी में पड़ जाते हैं। "
           "आखिर में दोनों मिलकर समस्या हल करते हैं और खुशी-खुशी गाँव लौट आते हैं।"),
    height=180,
)

c1, c2, c3 = st.columns(3)
with c1:
    create = st.button("✨ Create Job", type="primary", use_container_width=True)
with c2:
    demo = st.button("🎭 Demo Story", use_container_width=True)
with c3:
    st.button("🔄 Refresh", use_container_width=True)

if demo:
    st.session_state["story"] = (
        "गोलू और मोटू गाँव में रास्ता भूल जाते हैं। "
        "उन्हें एक छोटी नदी मिलती है। "
        "मोटू मजेदार तरीके से नदी पार करने की कोशिश करता है। "
        "गोलू हँसते-हँसते उसे सही रास्ता दिखाता है। "
        "दोनों सुरक्षित घर लौट आते हैं।"
    )
    st.rerun()

if "story" in st.session_state:
    story = st.session_state["story"]

if create:
    jobs = load_jobs()
    active = sum(1 for j in jobs if j.get("status") in ["Queued", "Generating", "Assembling"])
    if active >= 5:
        st.error("Queue में पहले से 5 active jobs हैं।")
    else:
        job = make_job(story, chars, lang, fmt, minutes)
        jobs.insert(0, job)
        save_jobs(jobs)
        st.success(f"Job {job['id']} queue में जोड़ दिया गया।")
        st.rerun()

st.divider()
st.subheader("🚀 AI Render")

api_key = st.text_input(
    "Pollo API Key",
    type="password",
    value=os.getenv("POLLO_API_KEY", ""),
    help="Production में Streamlit Secrets / environment variable में रखें।"
)

st.caption("AI clips 10 seconds के होंगे और फिर automatically एक 3–4 minute MP4 में जुड़ेंगे.")

jobs = load_jobs()
queued = [j for j in jobs if j.get("status") == "Queued"]

if queued:
    selected = st.selectbox("Render करने के लिए Job चुनें", [j["id"] for j in queued])

    if st.button("▶️ Start AI Rendering", type="primary", use_container_width=True):
        if not api_key:
            st.error("पहले Pollo API key डालें.")
        else:
            job = next((j for j in jobs if j["id"] == selected), None)
            if job:
                work = OUTPUT / f"job_{job['id']}"
                work.mkdir(exist_ok=True)
                clips = []
                try:
                    job["status"] = "Generating"
                    save_jobs(jobs)

                    total = len(job["scenes"])
                    progress = st.progress(0, text="AI scene generation शुरू...")
                    aspect = job["format"]

                    for idx, scene in enumerate(job["scenes"], 1):
                        progress.progress((idx - 1) / total, text=f"AI scene {idx}/{total} generate हो रहा है...")
                        task_id = pollo_video(api_key, scene["prompt"], aspect)
                        video_url = pollo_wait(api_key, task_id)
                        clip = work / f"scene_{idx:03d}.mp4"
                        download(video_url, clip)
                        clips.append(clip)

                    job["status"] = "Assembling"
                    save_jobs(jobs)
                    progress.progress(0.98, text="सभी clips को MP4 में जोड़ा जा रहा है...")

                    final = OUTPUT / f"cartoonflow_ai_{job['id']}.mp4"
                    concat_videos(clips, final)

                    job["status"] = "Complete"
                    job["output"] = str(final.relative_to(BASE))
                    save_jobs(jobs)
                    progress.progress(1.0, text="Complete")
                    st.success("🎉 असली AI-generated video तैयार है!")
                    st.video(str(final))
                    with open(final, "rb") as f:
                        st.download_button(
                            "⬇️ Download Final MP4",
                            f, file_name=final.name, mime="video/mp4",
                            use_container_width=True
                        )
                except Exception as e:
                    job["status"] = "Failed"
                    job["error"] = str(e)
                    save_jobs(jobs)
                    st.error(f"AI render failed: {e}")

st.divider()
st.subheader("🎞️ Generation Queue")
for j in load_jobs():
    with st.container(border=True):
        a, b, c = st.columns(3)
        a.write(f"**Job:** {j['id']}")
        b.write(f"**Length:** {j['minutes']} min")
        c.write(f"**Format:** {j['format']}")
        st.write(f"Language: {j['language']} | Status: **{j['status']}**")
        if j.get("error"):
            st.error(j["error"])
        if j.get("output"):
            p = BASE / j["output"]
            if p.exists():
                with open(p, "rb") as f:
                    st.download_button(
                        "⬇️ Download MP4", f, file_name=p.name,
                        mime="video/mp4", key=f"download_{j['id']}"
                    )
        with st.expander("🎬 Production Manifest"):
            st.write(f"Characters: {', '.join(c['name'] for c in j['characters'])}")
            st.write(f"AI clips: {len(j['scenes'])} × 10 seconds")
            st.json(j["scenes"][:2])

st.divider()
st.info(
    "यह version real cloud AI video generation के लिए Pollo API को जोड़ता है. "
    "API provider की pricing/limits अलग हैं. Android phone केवल control panel है; rendering cloud पर होती है."
)
