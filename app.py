import streamlit as st
from pathlib import Path
import json
import re
import uuid
import datetime
import subprocess
import shutil
import textwrap
import math

BASE = Path(__file__).parent
DATA = BASE / "data"
OUTPUT = BASE / "output"
DATA.mkdir(exist_ok=True)
OUTPUT.mkdir(exist_ok=True)
JOBS = DATA / "jobs.json"

if not JOBS.exists():
    JOBS.write_text("[]", encoding="utf-8")

st.set_page_config(
    page_title="CartoonFlow AI",
    page_icon="🎬",
    layout="wide",
)

def load_jobs():
    try:
        return json.loads(JOBS.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_jobs(jobs):
    JOBS.write_text(
        json.dumps(jobs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def make_scenes(story, chars, minutes):
    count = int(minutes * 10)  # 6 seconds per scene
    parts = [x.strip() for x in re.split(r"(?<=[.!?।])\s+|\n+", story) if x.strip()]

    if not parts:
        parts = [
            "गाँव की सुबह होती है।",
            "हीरो और उसका दोस्त एक मजेदार काम शुरू करते हैं।",
            "अचानक एक मजेदार समस्या आ जाती है।",
            "दोनों मिलकर समस्या का हल खोजते हैं।",
            "कहानी खुशहाल अंत के साथ खत्म होती है।",
        ]

    character_text = ", ".join(
        f"{c['name']} ({c['role']}): {c['look']}" for c in chars
    )

    scenes = []
    for i in range(count):
        line = parts[i % len(parts)]
        scenes.append(
            {
                "scene": i + 1,
                "duration": 6,
                "prompt": (
                    "3D family-friendly cartoon animation, cinematic village setting. "
                    f"Characters: {character_text}. "
                    f"Action: {line}. "
                    "Keep every character's face, body proportions, hairstyle, "
                    "clothes and colors consistent. Expressive faces, smooth camera "
                    "movement, bright lighting, no text, no watermark."
                ),
            }
        )
    return scenes

def make_job(story, chars, lang, fmt, minutes):
    job_id = str(uuid.uuid4())[:8]
    return {
        "id": job_id,
        "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Queued",
        "language": lang,
        "format": "16:9" if fmt.startswith("16") else "9:16",
        "minutes": int(minutes),
        "story": story,
        "characters": chars,
        "scenes": make_scenes(story, chars, minutes),
        "output": None,
        "error": None,
    }

def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

def render_demo(job):
    """
    Creates a real MP4 demo without an AI API.
    It uses generated cartoon-style scene cards and camera-motion effects.
    Replace this function later with an image/video AI worker.
    """
    from PIL import Image, ImageDraw, ImageFont

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg नहीं मिला। requirements.txt में imageio-ffmpeg रखें और app को restart करें."
        )

    out = OUTPUT / f"cartoonflow_{job['id']}.mp4"
    temp_dir = OUTPUT / f"frames_{job['id']}"
    temp_dir.mkdir(exist_ok=True)

    fmt = job["format"]
    if fmt == "16:9":
        W, H = 1280, 720
    else:
        W, H = 720, 1280

    fps = 12
    scenes = job["scenes"]

    try:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
        font_path = next((p for p in font_paths if Path(p).exists()), None)
        font = ImageFont.truetype(font_path, 42) if font_path else ImageFont.load_default()
        small = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()

        # Demo uses 1 generated frame every 0.25 sec to keep cloud rendering practical.
        # FFmpeg then creates the requested 6-second scene duration.
        for idx, scene in enumerate(scenes, start=1):
            img = Image.new("RGB", (W, H), (242, 231, 200))
            d = ImageDraw.Draw(img)

            # simple cartoon village background
            horizon = int(H * 0.58)
            d.rectangle([0, horizon, W, H], fill=(126, 190, 95))
            d.rectangle([0, 0, W, horizon], fill=(150, 205, 245))
            d.ellipse([W - 180, 55, W - 70, 165], fill=(255, 220, 90))

            # houses
            for x in range(60, W, max(260, W // 4)):
                y = horizon - 120
                d.rectangle([x, y, x + 150, horizon], fill=(230, 170, 105))
                d.polygon([(x - 15, y), (x + 75, y - 80), (x + 165, y)], fill=(170, 85, 60))

            # character placeholders as friendly cartoon circles/bodies
            colors = [(250, 210, 170), (180, 190, 200), (245, 190, 120), (180, 230, 150)]
            base_y = horizon - 15
            for ci, c in enumerate(job["characters"][:4]):
                cx = int(W * (0.2 + 0.2 * ci))
                cy = base_y - 130
                skin = colors[ci % len(colors)]
                d.ellipse([cx - 45, cy - 45, cx + 45, cy + 45], fill=skin, outline=(50, 50, 50), width=3)
                d.rectangle([cx - 55, cy + 45, cx + 55, cy + 155], fill=(70 + ci * 30, 120, 190))
                d.ellipse([cx - 25, cy - 18, cx - 15, cy - 8], fill=(20, 20, 20))
                d.ellipse([cx + 15, cy - 18, cx + 25, cy - 8], fill=(20, 20, 20))
                d.arc([cx - 20, cy - 5, cx + 20, cy + 25], 0, 180, fill=(80, 30, 30), width=3)
                d.text((cx - 60, cy + 175), c["name"], font=small, fill=(30, 30, 30))

            # scene title
            title = f"Scene {idx}/{len(scenes)}"
            d.rounded_rectangle([25, 20, W - 25, 92], radius=18, fill=(255, 255, 255))
            d.text((45, 38), title, font=font, fill=(35, 35, 35))

            # story line
            text = scene["prompt"]
            wrapped = textwrap.fill(text, width=48 if fmt == "9:16" else 90)
            box_y = int(H * 0.72)
            d.rounded_rectangle([35, box_y, W - 35, H - 35], radius=20, fill=(255, 255, 255))
            d.multiline_text((55, box_y + 25), wrapped, font=small, fill=(40, 40, 40), spacing=8)

            frame = temp_dir / f"scene_{idx:03d}.jpg"
            img.save(frame, quality=90)

        # Build the MP4 from scene cards. Each image lasts 6 seconds.
        concat = temp_dir / "concat.txt"
        with concat.open("w", encoding="utf-8") as f:
            for idx in range(1, len(scenes) + 1):
                frame = temp_dir / f"scene_{idx:03d}.jpg"
                f.write(f"file '{frame.as_posix()}'\n")
                f.write("duration 6\n")
            last = temp_dir / f"scene_{len(scenes):03d}.jpg"
            f.write(f"file '{last.as_posix()}'\n")

        cmd = [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat),
            "-vf", f"scale={W}:{H},format=yuv420p",
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-movflags", "+faststart",
            str(out),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-3000:])

        return out

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

st.title("🎬 CartoonFlow AI")
st.caption("Android-first 3D cartoon video production dashboard")

with st.sidebar:
    st.header("Project")
    lang = st.selectbox("Language", ["Hindi", "English", "Hinglish"])
    fmt = st.selectbox("Format", ["16:9 YouTube", "9:16 Shorts"])
    minutes = st.slider("Video length", 3, 4, 4)

    st.divider()
    st.header("Characters")
    count = st.number_input("Characters", min_value=1, max_value=6, value=2, step=1)

    defaults = [
        ("Golu", "Hero", "7-year-old Indian boy, round friendly face, black hair, yellow T-shirt, blue shorts, red shoes"),
        ("Motu", "Friend", "cute gray elephant, big expressive eyes, blue scarf, friendly smile"),
    ]

    chars = []
    for i in range(int(count)):
        d = defaults[i] if i < len(defaults) else (
            f"Character {i+1}", "Supporting", "friendly 3D cartoon character"
        )
        with st.expander(d[0], expanded=(i < 2)):
            name = st.text_input("Name", d[0], key=f"name_{i}")
            role = st.text_input("Role", d[1], key=f"role_{i}")
            look = st.text_area("Fixed appearance", d[2], key=f"look_{i}", height=90)
            chars.append({"name": name, "role": role, "look": look})

story = st.text_area(
    "📜 कहानी",
    value=(
        "गोलू और मोटू गाँव में जंगल की ओर जाते हैं। "
        "रास्ते में उन्हें एक चमकता हुआ आम मिलता है। "
        "दोनों आम को लेकर मजेदार परेशानी में पड़ जाते हैं। "
        "आखिर में दोनों मिलकर समस्या हल करते हैं और खुशी-खुशी गाँव लौट आते हैं।"
    ),
    height=180,
)

c1, c2, c3 = st.columns(3)

with c1:
    create = st.button("✨ Create Job", type="primary", use_container_width=True)

with c2:
    demo = st.button("🎭 Demo Story", use_container_width=True)

with c3:
    refresh = st.button("🔄 Refresh Queue", use_container_width=True)

if demo:
    story = (
        "गोलू और मोटू गाँव में रास्ता भूल जाते हैं। "
        "उन्हें एक छोटी नदी मिलती है। "
        "मोटू मजेदार तरीके से नदी पार करने की कोशिश करता है। "
        "गोलू हँसते-हँसते उसे सही रास्ता दिखाता है। "
        "दोनों सुरक्षित घर लौट आते हैं।"
    )
    st.session_state["story"] = story
    st.rerun()

if "story" in st.session_state:
    story = st.session_state["story"]

if create:
    jobs = load_jobs()
    active = sum(1 for x in jobs if x.get("status") in ["Queued", "Generating", "Assembling"])

    if active >= 5:
        st.error("Queue में पहले से 5 active jobs हैं।")
    else:
        job = make_job(story, chars, lang, fmt, minutes)
        jobs.insert(0, job)
        save_jobs(jobs)
        st.success(f"Job {job['id']} queue में जोड़ दिया गया।")
        st.rerun()

st.divider()
st.subheader("🚀 Render Video")

render_mode = st.radio(
    "Rendering mode",
    ["Demo renderer (no API key)", "AI mode (external API)"],
    horizontal=True,
)

if render_mode.startswith("Demo"):
    st.info(
        "Demo mode बिना AI API key के एक वास्तविक MP4 बनाता है। "
        "यह test/render pipeline है, photoreal AI animation नहीं।"
    )
else:
    st.warning(
        "AI mode के लिए external image/video provider API जोड़ना होगा। "
        "API key और provider limits/charges लागू हो सकते हैं।"
    )

jobs = load_jobs()
queued = [j for j in jobs if j.get("status") == "Queued"]

if queued:
    selected_id = st.selectbox(
        "Render करने के लिए Job चुनें",
        [j["id"] for j in queued],
    )

    if st.button("▶️ Start Rendering", type="primary", use_container_width=True):
        job = next((j for j in jobs if j["id"] == selected_id), None)

        if job:
            if render_mode.startswith("AI"):
                st.error(
                    "AI mode अभी external API worker से connect नहीं है। "
                    "पहले Demo renderer test करें."
                )
            else:
                try:
                    job["status"] = "Generating"
                    save_jobs(jobs)

                    with st.spinner("MP4 render हो रहा है..."):
                        output = render_demo(job)

                    job["status"] = "Complete"
                    job["output"] = str(output.relative_to(BASE))
                    save_jobs(jobs)

                    st.success("MP4 तैयार है।")
                    st.video(str(output))
                    with open(output, "rb") as video_file:
                        st.download_button(
                            "⬇️ Download MP4",
                            data=video_file,
                            file_name=output.name,
                            mime="video/mp4",
                            use_container_width=True,
                        )

                except Exception as e:
                    job["status"] = "Failed"
                    job["error"] = str(e)
                    save_jobs(jobs)
                    st.error(f"Render failed: {e}")

st.divider()
st.subheader("🎞️ Generation Queue")

jobs = load_jobs()

if not jobs:
    st.info("अभी कोई video job नहीं है।")
else:
    for j in jobs:
        with st.container(border=True):
            a, b, c = st.columns([1, 1, 1])
            a.write(f"**Job:** {j['id']}")
            b.write(f"**Length:** {j['minutes']} min")
            c.write(f"**Format:** {j['format']}")

            st.write(
                f"Language: {j['language']} | Status: **{j['status']}**"
            )

            if j.get("error"):
                st.error(j["error"])

            if j.get("output"):
                output_path = BASE / j["output"]
                if output_path.exists():
                    with open(output_path, "rb") as vf:
                        st.download_button(
                            "⬇️ Download MP4",
                            data=vf,
                            file_name=output_path.name,
                            mime="video/mp4",
                            key=f"dl_{j['id']}",
                        )

            with st.expander("🎬 Scenes / Production Manifest"):
                st.write(f"Characters: {', '.join(x['name'] for x in j['characters'])}")
                st.write(f"Scenes: {len(j['scenes'])}")
                st.json(j["scenes"][:3])

            st.download_button(
                "📄 Download Job JSON",
                data=json.dumps(j, ensure_ascii=False, indent=2),
                file_name=f"cartoonflow_{j['id']}.json",
                mime="application/json",
                key=f"json_{j['id']}",
            )

st.divider()
st.subheader("⚙️ Production Backend")

st.markdown(
    """
**Android phone = control panel**

Current Demo pipeline:

**Story → scene plan → cartoon scene cards → 6-second scenes → MP4**

For true AI animation, the next production adapter can be connected as:

**Character reference → AI scene image → image-to-video clip → Hindi/English TTS → subtitles/SFX → FFmpeg → final MP4**

The dashboard is intentionally separate from the GPU renderer so it can later use a cloud GPU without changing the Android interface.
"""
)
