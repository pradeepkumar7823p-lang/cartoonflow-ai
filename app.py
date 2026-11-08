import streamlit as st
import json
import uuid
import datetime
import os
import subprocess
from pathlib import Path

from backend import render_job


BASE = Path(__file__).parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)

JOBS = DATA / "jobs.json"

if not JOBS.exists():
    JOBS.write_text("[]", encoding="utf-8")


st.set_page_config(
    page_title="CartoonFlow AI",
    page_icon="🎬",
    layout="wide"
)


def load_jobs():
    try:
        return json.loads(
            JOBS.read_text(encoding="utf-8")
        )
    except:
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


def scene_plan(story, chars, minutes):

    count = minutes * 4

    parts = [
        x.strip()
        for x in story.replace("।", ".").split(".")
        if x.strip()
    ]

    if not parts:

        parts = [
            "The story begins in an Indian village.",
            "The characters start a funny adventure.",
            "Something unexpected happens.",
            "The characters react with funny expressions.",
            "The story reaches a happy ending."
        ]

    char_text = ", ".join(
        [
            f"{c['name']} ({c['look']})"
            for c in chars
        ]
    )

    scenes = []

    for i in range(count):

        line = parts[i % len(parts)]

        scenes.append(
            {
                "scene": i + 1,
                "duration": 10,
                "prompt": (
                    f"Story action: {line}. "
                    f"Characters: {char_text}. "
                    f"Show natural 3D cartoon movement, "
                    f"expressive faces, cinematic camera motion, "
                    f"colorful Indian village environment."
                )
            }
        )

    return scenes


st.title("🎬 CartoonFlow AI")

st.caption(
    "Android-first 3D cartoon video generator"
)


with st.sidebar:

    st.header("⚙️ Project")

    language = st.selectbox(
        "Language",
        ["Hindi", "English", "Hinglish"]
    )

    fmt = st.selectbox(
        "Format",
        [
            "16:9 YouTube",
            "9:16 Shorts"
        ]
    )

    minutes = st.slider(
        "Video length",
        1,
        4,
        4
    )

    st.divider()

    st.header("👥 Characters")

    count = st.number_input(
        "Characters",
        min_value=1,
        max_value=6,
        value=2,
        step=1
    )

    chars = []

    defaults = [
        (
            "Golu",
            "Hero",
            "7-year-old Indian boy, round friendly face, black hair, yellow T-shirt, blue shorts, red shoes"
        ),
        (
            "Motu",
            "Friend",
            "cute grey elephant, big expressive eyes, blue scarf, friendly smile"
        )
    ]

    for i in range(int(count)):

        if i < len(defaults):
            d = defaults[i]
        else:
            d = (
                f"Character {i+1}",
                "Supporting",
                "friendly 3D cartoon character"
            )

        with st.expander(
            d[0],
            expanded=i < 2
        ):

            name = st.text_input(
                "Name",
                d[0],
                key=f"name_{i}"
            )

            role = st.text_input(
                "Role",
                d[1],
                key=f"role_{i}"
            )

            look = st.text_area(
                "Fixed appearance",
                d[2],
                key=f"look_{i}",
                height=100
            )

            chars.append(
                {
                    "name": name,
                    "role": role,
                    "look": look
                }
            )


st.header("📜 कहानी")

story = st.text_area(
    "Story",
    value=(
        "गोलू और मोटू गाँव में खेल रहे हैं। "
        "तभी उन्हें एक मजेदार चीज मिलती है। "
        "दोनों उसे लेकर गाँव में घूमते हैं और बहुत मजेदार घटनाएँ होती हैं। "
        "अंत में दोनों खुश होकर घर लौटते हैं।"
    ),
    height=180
)


c1, c2, c3 = st.columns(3)

with c1:

    create = st.button(
        "✨ Create Job",
        type="primary",
        use_container_width=True
    )

with c2:

    demo = st.button(
        "🎭 Demo Story",
        use_container_width=True
    )

with c3:

    refresh = st.button(
        "🔄 Refresh",
        use_container_width=True
    )


if demo:

    story = (
        "गोलू और मोटू गाँव में खेल रहे हैं। "
        "अचानक उन्हें एक बहुत बड़ा आम मिलता है। "
        "दोनों आम को घर ले जाने की कोशिश करते हैं। "
        "रास्ते में कई मजेदार घटनाएँ होती हैं। "
        "अंत में दोनों आम बाँटकर खुशी से खाते हैं।"
    )

    st.session_state["story"] = story
    st.rerun()


if "story" in st.session_state:

    story = st.session_state["story"]


if create:

    jobs = load_jobs()

    active = sum(
        1
        for x in jobs
        if x.get("status") in ["Queued", "Generating"]
    )

    if active >= 5:

        st.error(
            "एक समय में अधिकतम 5 active jobs रखे गए हैं।"
        )

    else:

        job_id = uuid.uuid4().hex[:8]

        job = {

            "id": job_id,

            "created":
                datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

            "status": "Queued",

            "language": language,

            "format":
                "16:9"
                if fmt.startswith("16")
                else "9:16",

            "minutes": minutes,

            "story": story,

            "characters": chars,

            "scenes":
                scene_plan(
                    story,
                    chars,
                    minutes
                )
        }

        jobs.insert(0, job)

        save_jobs(jobs)

        st.success(
            f"Job {job_id} queue में जोड़ दिया गया।"
        )


st.divider()


# ==========================
# AI RENDER
# ==========================

st.header("🚀 AI Render")

api_key = st.text_input(
    "Pollo API Key",
    type="password",
    help="Pollo API dashboard से API key डालें।"
)

st.caption(
    "हर AI clip 10 seconds का बनेगा और सभी clips automatically जोड़कर final MP4 बनाया जाएगा."
)


jobs = load_jobs()


if jobs:

    job_ids = [
        x["id"]
        for x in jobs
        if x.get("status") != "Complete"
    ]

    if job_ids:

        selected_job = st.selectbox(
            "Render करने के लिए Job चुनें",
            job_ids
        )

        if st.button(
            "▶️ Start AI Rendering",
            type="primary",
            use_container_width=True
        ):

            if not api_key.strip():

                st.error(
                    "पहले Pollo API Key डालें।"
                )

            else:

                job = next(
                    x
                    for x in jobs
                    if x["id"] == selected_job
                )

                job["status"] = "Generating"

                save_jobs(jobs)

                progress = st.progress(0)

                status_box = st.empty()

                def update_progress(
                    current,
                    total,
                    message
                ):

                    progress.progress(
                        min(
                            current / total,
                            1.0
                        )
                    )

                    status_box.info(
                        message
                    )

                try:

                    output = render_job(
                        job,
                        api_key,
                        update_progress
                    )

                    job["status"] = "Complete"

                    job["output"] = output

                    save_jobs(jobs)

                    progress.progress(1.0)

                    st.success(
                        "🎉 असली AI 3D video तैयार है!"
                    )

                    st.video(output)

                    with open(
                        output,
                        "rb"
                    ) as f:

                        st.download_button(
                            "⬇️ Download MP4",
                            f,
                            file_name=
                            f"CartoonFlow_{job['id']}.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )

                except Exception as e:

                    job["status"] = "Failed"

                    job["error"] = str(e)

                    save_jobs(jobs)

                    st.error(
                        "Rendering failed"
                    )

                    st.code(
                        str(e)
                    )


st.divider()


# ==========================
# QUEUE
# ==========================

st.header("🎞️ Generation Queue")


jobs = load_jobs()


if not jobs:

    st.info(
        "अभी कोई video job नहीं है।"
    )

else:

    for job in jobs:

        with st.container(border=True):

            a, b, c = st.columns(3)

            a.write(
                f"**Job:** {job['id']}"
            )

            b.write(
                f"**Length:** {job['minutes']} min"
            )

            c.write(
                f"**Format:** {job['format']}"
            )

            st.write(
                f"Language: {job['language']} | "
                f"Status: **{job['status']}**"
            )

            if job.get("output"):

                output = job["output"]

                if os.path.exists(output):

                    with open(
                        output,
                        "rb"
                    ) as f:

                        st.download_button(
                            "⬇️ Download MP4",
                            f,
                            file_name=
                            f"CartoonFlow_{job['id']}.mp4",
                            mime="video/mp4",
                            key=f"download_{job['id']}"
                        )

            with st.expander(
                "🎬 Production Manifest"
            ):

                st.write(
                    f"Scenes: {len(job['scenes'])}"
                )

                st.json(
                    job["scenes"]
                )


st.divider()

st.info(
    "📱 Android phone = control panel | "
    "☁️ AI video rendering = Pollo cloud API | "
    "🎬 Final MP4 = automatically assembled"
)
