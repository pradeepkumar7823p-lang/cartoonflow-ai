import streamlit as st
from pathlib import Path
import json
import uuid
import datetime
import subprocess
import shutil

BASE = Path(__file__).parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)

JOBS = DATA / "jobs.json"
OUTPUTS = DATA / "outputs"
OUTPUTS.mkdir(exist_ok=True)

if not JOBS.exists():
    JOBS.write_text("[]", encoding="utf-8")


st.set_page_config(
    page_title="CartoonFlow AI",
    page_icon="🎬",
    layout="wide"
)


# =========================
# JOB DATABASE
# =========================

def load_jobs():
    try:
        return json.loads(
            JOBS.read_text(encoding="utf-8")
        )
    except Exception:
        return []


def save_jobs(jobs):
    JOBS.write_text(
        json.dumps(
            jobs,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# =========================
# SCENE GENERATOR
# =========================

def make_scenes(story, characters, minutes):

    total_scenes = int(minutes) * 10

    parts = [
        x.strip()
        for x in story.replace("\n", " ").split("।")
        if x.strip()
    ]

    if not parts:
        parts = [
            "कहानी शुरू होती है।",
            "हीरो अपने दोस्त के साथ गाँव में जाता है।",
            "उन्हें एक मजेदार समस्या दिखाई देती है।",
            "दोनों समस्या को हल करने की कोशिश करते हैं।",
            "अचानक कहानी में मजेदार मोड़ आता है।",
            "सब मिलकर समस्या हल करते हैं।",
            "कहानी खुशी के साथ समाप्त होती है।"
        ]

    character_text = ", ".join(
        f'{c["name"]}: {c["look"]}'
        for c in characters
    )

    scenes = []

    for i in range(total_scenes):

        action = parts[i % len(parts)]

        scenes.append({
            "scene": i + 1,
            "duration": 6,
            "prompt": (
                "3D family friendly Indian cartoon animation. "
                f"Characters: {character_text}. "
                f"Action: {action}. "
                "Keep exactly the same character faces, clothes, "
                "body proportions and colors. "
                "Bright cinematic village environment. "
                "Expressive faces. "
                "No text. No watermark."
            )
        })

    return scenes


# =========================
# JOB CREATOR
# =========================

def create_job(
    story,
    language,
    format_value,
    minutes,
    characters
):

    job = {
        "id": str(uuid.uuid4())[:8],
        "created": datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "status": "Queued",
        "language": language,
        "format": format_value,
        "minutes": int(minutes),
        "story": story,
        "characters": characters,
        "scenes": make_scenes(
            story,
            characters,
            minutes
        ),
        "output": None,
        "error": None
    }

    return job


# =========================
# FFMPEG
# =========================

def get_ffmpeg():

    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:
        return ffmpeg

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


# =========================
# DEMO MP4 RENDERER
# =========================

def render_demo(job):

    ffmpeg = get_ffmpeg()

    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg उपलब्ध नहीं है। "
            "requirements.txt check करें।"
        )

    from PIL import Image, ImageDraw, ImageFont

    job_folder = (
        OUTPUTS / job["id"]
    )

    frames_folder = (
        job_folder / "frames"
    )

    frames_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    if job["format"] == "16:9":

        W = 1280
        H = 720

    else:

        W = 720
        H = 1280

    font_candidates = [

        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",

        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"

    ]

    font_path = next(
        (
            p for p in font_candidates
            if Path(p).exists()
        ),
        None
    )

    if font_path:

        big_size = max(
            30,
            W // 22
        )

        small_size = max(
            20,
            W // 40
        )

        big_font = ImageFont.truetype(
            font_path,
            big_size
        )

        small_font = ImageFont.truetype(
            font_path,
            small_size
        )

    else:

        big_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    scenes = job["scenes"]

    total = len(scenes)

    # Create scene images

    for index, scene in enumerate(scenes):

        image = Image.new(
            "RGB",
            (W, H),
            (245, 235, 210)
        )

        draw = ImageDraw.Draw(image)

        padding = int(
            min(W, H) * 0.08
        )

        draw.rounded_rectangle(
            (
                padding,
                padding,
                W - padding,
                H - padding
            ),
            radius=30,
            fill=(255, 248, 235),
            outline=(80, 80, 80),
            width=4
        )

        title = (
            f"CartoonFlow AI • "
            f"Scene {scene['scene']}/{total}"
        )

        draw.text(
            (
                padding + 25,
                padding + 25
            ),
            title,
            font=small_font,
            fill=(30, 30, 30)
        )

        character_names = " • ".join(
            c["name"]
            for c in job["characters"]
        )

        draw.text(
            (
                padding + 25,
                padding + 80
            ),
            character_names,
            font=small_font,
            fill=(70, 70, 70)
        )

        action = (
            scene["prompt"]
            .split("Action:", 1)[-1]
            .split("Keep exactly", 1)[0]
            .strip()
        )

        max_width = (
            W - 2 * (padding + 55)
        )

        words = action.split()

        lines = []
        current = ""

        for word in words:

            test = (
                current + " " + word
            ).strip()

            box = draw.textbbox(
                (0, 0),
                test,
                font=big_font
            )

            if box[2] <= max_width:

                current = test

            else:

                if current:
                    lines.append(current)

                current = word

        if current:
            lines.append(current)

        y = (
            H // 2
            - len(lines) * 30
        )

        for line in lines[:8]:

            box = draw.textbbox(
                (0, 0),
                line,
                font=big_font
            )

            text_width = (
                box[2] - box[0]
            )

            x = (
                W - text_width
            ) / 2

            draw.text(
                (x, y),
                line,
                font=big_font,
                fill=(25, 25, 25)
            )

            y += 60

        draw.text(
            (
                padding + 25,
                H - padding - 45
            ),
            "CartoonFlow AI Demo Render",
            font=small_font,
            fill=(100, 100, 100)
        )

        frame_path = (
            frames_folder /
            f"scene_{index:03d}.png"
        )

        image.save(frame_path)

    # =========================
    # CREATE VIDEO
    # =========================

    output_file = (
        OUTPUTS /
        f"CartoonFlow_{job['id']}_"
        f"{job['format'].replace(':', 'x')}.mp4"
    )

    concat_file = (
        job_folder /
        "concat.txt"
    )

    with concat_file.open(
        "w",
        encoding="utf-8"
    ) as f:

        for index in range(total):

            frame = (
                frames_folder /
                f"scene_{index:03d}.png"
            )

            f.write(
                f"file '{frame.as_posix()}'\n"
            )

            f.write(
                "duration 6\n"
            )

        last_frame = (
            frames_folder /
            f"scene_{total - 1:03d}.png"
        )

        f.write(
            f"file '{last_frame.as_posix()}'\n"
        )

    command = [

        ffmpeg,

        "-y",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        str(concat_file),

        "-vf",
        f"scale={W}:{H},format=yuv420p",

        "-r",
        "30",

        "-movflags",
        "+faststart",

        str(output_file)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=900
    )

    if result.returncode != 0:

        raise RuntimeError(
            result.stderr[-3000:]
        )

    return str(output_file)


# =========================
# HEADER
# =========================

st.title("🎬 CartoonFlow AI")

st.caption(
    "Android-first 3D cartoon video production dashboard"
)


# =========================
# SIDEBAR
# =========================

with st.sidebar:

    st.header("Project")

    language = st.selectbox(
        "Language",
        [
            "Hindi",
            "English",
            "Hinglish"
        ]
    )

    video_format = st.selectbox(
        "Format",
        [
            "16:9 YouTube",
            "9:16 Shorts"
        ]
    )

    minutes = st.slider(
        "Video length",
        min_value=3,
        max_value=4,
        value=4
    )

    st.divider()

    st.header("Characters")

    character_count = st.number_input(
        "Characters",
        min_value=1,
        max_value=6,
        value=2,
        step=1
    )

    defaults = [

        (
            "Golu",
            "Hero",
            "7-year-old Indian boy, "
            "round friendly face, black hair, "
            "yellow T-shirt, blue shorts, red shoes"
        ),

        (
            "Motu",
            "Friend",
            "cute gray elephant, "
            "big expressive eyes, blue scarf, "
            "friendly smile"
        )
    ]

    characters = []

    for i in range(
        int(character_count)
    ):

        if i < len(defaults):

            default = defaults[i]

        else:

            default = (
                f"Character {i + 1}",
                "Supporting",
                "friendly 3D cartoon character"
            )

        with st.expander(
            default[0],
            expanded=(i < 2)
        ):

            name = st.text_input(
                "Name",
                default[0],
                key=f"name_{i}"
            )

            role = st.text_input(
                "Role",
                default[1],
                key=f"role_{i}"
            )

            appearance = st.text_area(
                "Fixed appearance",
                default[2],
                key=f"appearance_{i}",
                height=90
            )

            characters.append({
                "name": name,
                "role": role,
                "look": appearance
            })


# =========================
# STORY
# =========================

story = st.text_area(
    "📜 कहानी",
    value=(
        "गोलू और मोटू हाथी गाँव से जंगल की ओर जाते हैं। "
        "रास्ते में उन्हें एक मजेदार आम मिलता है। "
        "दोनों आम को लेकर मजेदार परेशानी में पड़ जाते हैं। "
        "आखिर में दोनों मिलकर समस्या हल करते हैं और "
        "खुशी-खुशी घर लौटते हैं।"
    ),
    height=170
)


# =========================
# BUTTONS
# =========================

col1, col2, col3 = st.columns(3)

with col1:

    create_job_button = st.button(
        "✨ Create Job",
        type="primary",
        use_container_width=True
    )

with col2:

    demo_button = st.button(
        "🎭 Demo Story",
        use_container_width=True
    )

with col3:

    refresh_button = st.button(
        "🔄 Refresh Queue",
        use_container_width=True
    )


if demo_button:

    st.session_state["story"] = (
        "गोलू और मोटू हाथी गाँव में एक आम ढूँढते हैं। "
        "दोनों आम को लेकर मजेदार बहस करते हैं। "
        "अचानक आम लुढ़ककर तालाब में चला जाता है। "
        "दोनों मिलकर उसे बाहर निकालते हैं और "
        "खुशी से घर लौटते हैं।"
    )

    st.rerun()


if "story" in st.session_state:

    story = st.session_state["story"]


# =========================
# CREATE JOB
# =========================

if create_job_button:

    jobs = load_jobs()

    active_jobs = sum(
        1
        for job in jobs
        if job.get("status")
        in [
            "Queued",
            "Generating",
            "Assembling"
        ]
    )

    if active_jobs >= 5:

        st.error(
            "Queue में पहले से 5 active jobs हैं।"
        )

    else:

        job = create_job(
            story,
            language,
            (
                "16:9"
                if video_format.startswith("16")
                else "9:16"
            ),
            minutes,
            characters
        )

        jobs.insert(
            0,
            job
        )

        save_jobs(jobs)

        st.success(
            f"✅ Job {job['id']} queue में जोड़ दिया गया।"
        )

        st.rerun()


# =========================
# RENDER
# =========================

st.divider()

st.subheader(
    "🚀 Render Video"
)

jobs = load_jobs()


if jobs:

    render_mode = st.radio(
        "Rendering mode",
        [
            "Demo render",
            "AI images + motion"
        ],
        index=0,
        horizontal=True
    )

    if render_mode == "AI images + motion":

        st.warning(
            "AI mode अभी external AI provider "
            "API के लिए रखा गया है। "
            "पहले Demo render से MP4 pipeline test करें।"
        )

    queued_jobs = [
        job
        for job in jobs
        if job.get("status") == "Queued"
    ]

    if queued_jobs:

        selected_job = st.selectbox(
            "Queued job चुनें",
            [
                job["id"]
                for job in queued_jobs
            ]
        )

        if st.button(
            "▶️ Start Rendering",
            type="primary",
            use_container_width=True
        ):

            if render_mode == "AI images + motion":

                st.info(
                    "AI mode के लिए API integration "
                    "अभी बाकी है। Demo render चुनें।"
                )

            else:

                selected = next(
                    job
                    for job in jobs
                    if job["id"]
                    == selected_job
                )

                selected["status"] = "Generating"

                save_jobs(jobs)

                progress = st.progress(
                    0
                )

                status_text = st.empty()

                try:

                    status_text.info(
                        "🎬 MP4 rendering शुरू..."
                    )

                    output = render_demo(
                        selected
                    )

                    progress.progress(
                        100
                    )

                    selected["status"] = (
                        "Complete"
                    )

                    selected["output"] = (
                        output
                    )

                    selected["error"] = None

                    save_jobs(jobs)

                    st.success(
                        "🎉 MP4 तैयार है!"
                    )

                    st.rerun()

                except Exception as error:

                    selected["status"] = (
                        "Failed"
                    )

                    selected["error"] = (
                        str(error)
                    )

                    save_jobs(jobs)

                    st.error(
                        "❌ Rendering fail हुआ।"
                    )

                    st.exception(
                        error
                    )

    else:

        st.info(
            "कोई queued job नहीं है।"
        )


# =========================
# QUEUE MANAGEMENT
# =========================

st.divider()

st.subheader(
    "🧹 Queue Management"
)

q1, q2 = st.columns(2)


with q1:

    if st.button(
        "🗑️ Clear completed/failed",
        use_container_width=True
    ):

        remaining = [
            job
            for job in load_jobs()
            if job.get("status")
            not in [
                "Complete",
                "Failed"
            ]
        ]

        save_jobs(
            remaining
        )

        st.success(
            "Completed/failed jobs हटाए गए।"
        )

        st.rerun()


with q2:

    if st.button(
        "⚠️ Clear ALL jobs",
        use_container_width=True
    ):

        save_jobs([])

        st.success(
            "सभी jobs clear कर दी गईं।"
        )

        st.rerun()


# =========================
# GENERATION QUEUE
# =========================

st.divider()

st.subheader(
    "🎞️ Generation Queue"
)

jobs = load_jobs()


if not jobs:

    st.info(
        "अभी कोई video job नहीं है।"
    )

else:

    for job in jobs:

        with st.container(
            border=True
        ):

            c1, c2, c3 = st.columns(
                [2, 2, 2]
            )

            with c1:

                st.write(
                    f"**Job:** `{job['id']}`"
                )

                st.write(
                    f"Length: "
                    f"{job['minutes']} min"
                )

            with c2:

                st.write(
                    f"Format: "
                    f"{job['format']}"
                )

                st.write(
                    f"Language: "
                    f"{job['language']}"
                )

            with c3:

                status = job.get(
                    "status",
                    "Queued"
                )

                if status == "Complete":

                    st.success(
                        "Complete"
                    )

                elif status == "Failed":

                    st.error(
                        "Failed"
                    )

                elif status == "Generating":

                    st.warning(
                        "Generating"
                    )

                else:

                    st.info(
                        "Queued"
                    )

            if (
                job.get("output")
                and Path(
                    job["output"]
                ).exists()
            ):

                with open(
                    job["output"],
                    "rb"
                ) as video_file:

                    st.download_button(
                        "⬇️ Download MP4",
                        data=video_file.read(),
                        file_name=Path(
                            job["output"]
                        ).name,
                        mime="video/mp4",
                        key=(
                            f"video_"
                            f"{job['id']}"
                        ),
                        use_container_width=True
                    )

            if job.get("error"):

                with st.expander(
                    "❌ Error"
                ):

                    st.code(
                        job["error"]
                    )

            with st.expander(
                "🎬 Scenes / Production Manifest"
            ):

                st.write(
                    "Characters: "
                    + ", ".join(
                        c["name"]
                        for c in job["characters"]
                    )
                )

                st.write(
                    f"Scenes: "
                    f"{len(job['scenes'])}"
                )

                st.download_button(
                    "📄 Download Job JSON",
                    data=json.dumps(
                        job,
                        ensure_ascii=False,
                        indent=2
                    ),
                    file_name=(
                        f"cartoonflow_"
                        f"{job['id']}.json"
                    ),
                    mime="application/json",
                    key=(
                        f"json_"
                        f"{job['id']}"
                    )
                )


# =========================
# BACKEND INFO
# =========================

st.divider()

st.subheader(
    "⚙️ Production Backend"
)

st.markdown(
    """
**📱 Android phone = control panel**

**Demo mode:** वास्तविक MP4 बनाता है।

**Production AI chain:**

Story  
↓  
Character consistency  
↓  
Scene images  
↓  
6-second animation clips  
↓  
Hindi/English voice  
↓  
Subtitles + SFX  
↓  
FFmpeg  
↓  
Final MP4
"""
)

st.info(
    "अभी Demo mode बिना API key के चलता है। "
    "अगले चरण में इसी dashboard में वास्तविक "
    "AI cartoon image/video generation जोड़ सकते हैं।"
        )2
