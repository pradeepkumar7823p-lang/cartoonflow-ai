import streamlit as st
from pathlib import Path
import json
import re
import uuid
import datetime

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
    return json.loads(JOBS.read_text(encoding="utf-8"))


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
    n = minutes * 10

    parts = [
        x.strip()
        for x in re.split(r"(?<=[।!?])\s+", story)
        if x.strip()
    ]

    if not parts:
        parts = [
            "A cheerful village story begins.",
            "The characters start a funny adventure.",
            "Something unexpected happens.",
            "Everyone reacts with funny expressions.",
            "The story reaches a happy ending."
        ]

    char_text = ", ".join(
        f"{c['name']} ({c['look']})"
        for c in chars
    )

    scenes = []

    for i in range(n):
        line = parts[i % len(parts)]

        scenes.append({
            "scene": i + 1,
            "duration": 6,
            "prompt": (
                "3D family friendly cartoon animation. "
                f"Characters: {char_text}. "
                f"Action: {line}. "
                "Keep character faces, body proportions, "
                "clothes and colors consistent. "
                "Cinematic camera, expressive faces, "
                "bright village environment, no text, no watermark."
            )
        })

    return scenes


st.title("🎬 CartoonFlow AI")

st.caption(
    "Android-first 3D cartoon video production dashboard"
)

with st.sidebar:

    st.header("Project")

    lang = st.selectbox(
        "Language",
        ["Hindi", "English", "Hinglish"]
    )

    fmt = st.selectbox(
        "Format",
        ["16:9 YouTube", "9:16 Shorts"]
    )

    minutes = st.slider(
        "Video length",
        3,
        4,
        4
    )

    st.divider()

    st.header("Characters")

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
            "cute gray elephant, big expressive eyes, blue scarf, friendly smile"
        )
    ]

    for i in range(int(count)):

        if i < len(defaults):
            d = defaults[i]
        else:
            d = (
                f"Character {i + 1}",
                "Supporting",
                "friendly 3D cartoon character"
            )

        with st.expander(
            f"{d[0]}",
            expanded=(i < 2)
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
                height=80
            )

            chars.append({
                "name": name,
                "role": role,
                "look": look
            })


story = st.text_area(
    "📜 कहानी",
    value=(
        "गोलू और मोटू हाथी गांव से जंगल की ओर जाते हैं। "
        "रास्ते में उन्हें एक चमकता हुआ आम मिलता है। "
        "दोनों आम को लेकर मजेदार परेशानी में फंस जाते हैं। "
        "आखिर में दोनों हंसते हुए घर लौट आते हैं।"
    ),
    height=170
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
        "🔄 Refresh Queue",
        use_container_width=True
    )


if demo:

    demo_story = (
        "गोलू और मोटू जंगल में रास्ता भूल जाते हैं। "
        "उन्हें एक छोटी नदी मिलती है। "
        "दोनों मजेदार तरीके से नदी पार करने की कोशिश करते हैं। "
        "आखिर में उन्हें सही रास्ता मिल जाता है और दोनों खुशी से घर लौटते हैं।"
    )

    st.session_state["story"] = demo_story

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
            "Queue में पहले से 5 active jobs हैं।"
        )

    else:

        job = {
            "id": str(uuid.uuid4())[:8],

            "created": datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "status": "Queued",

            "language": lang,

            "format": (
                "16:9"
                if fmt.startswith("16")
                else "9:16"
            ),

            "minutes": minutes,

            "story": story,

            "characters": chars,

            "scenes": scene_plan(
                story,
                chars,
                minutes
            )
        }

        jobs.insert(0, job)

        save_jobs(jobs)

        st.success(
            f"Job {job['id']} queue में जोड़ दिया गया।"
        )


st.divider()

st.subheader("🎞️ Generation Queue")

jobs = load_jobs()


if not jobs:

    st.info("अभी कोई video job नहीं है।")

else:

    for j in jobs:

        with st.container(border=True):

            a, b, c = st.columns([1, 2, 2])

            with a:
                st.write(f"**Job:** {j['id']}")

            with b:
                st.write(
                    f"**Length:** {j['minutes']} min"
                )

            with c:
                st.write(
                    f"**Format:** {j['format']}"
                )

            st.write(
                f"**Language:** {j['language']}"
            )

            st.write(
                f"**Status:** {j['status']}"
            )

            with st.expander(
                "🎬 Scenes / Production Manifest"
            ):

                st.write(
                    "Characters: "
                    + ", ".join(
                        x["name"]
                        for x in j["characters"]
                    )
                )

                st.write(
                    f"Scenes: {len(j['scenes'])}"
                )

                st.download_button(
                    "⬇️ Download Job JSON",
                    data=json.dumps(
                        j,
                        ensure_ascii=False,
                        indent=2
                    ),
                    file_name=f"cartoonflow_{j['id']}.json",
                    mime="application/json"
                )


st.divider()

st.subheader("⚙️ Production Backend")

st.markdown(
    """
**Android phone = control panel**

Actual AI video generation should run on a remote GPU backend.

Recommended production chain:

Character reference
→ Scene image
→ 6-second image-to-video clips
→ Hindi/English TTS
→ Subtitles + SFX
→ FFmpeg assembly
→ Final MP4
"""
)

st.warning(
    "यह dashboard अभी production queue और scene manifests बनाता है। "
    "Actual AI rendering के लिए GPU backend connect करना होगा।"
    )
