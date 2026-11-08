
import streamlit as st
from pathlib import Path
import json, re, uuid, datetime

BASE=Path(__file__).parent
DATA=BASE/"data"; DATA.mkdir(exist_ok=True)
JOBS=DATA/"jobs.json"
if not JOBS.exists(): JOBS.write_text("[]",encoding="utf-8")

st.set_page_config(page_title="CartoonFlow AI Mobile", page_icon="🎬", layout="wide")

def load_jobs():
    return json.loads(JOBS.read_text(encoding="utf-8"))
def save_jobs(j):
    JOBS.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding="utf-8")
def scene_plan(story, chars, minutes):
    n=minutes*10
    parts=[x.strip() for x in re.split(r'(?<=[.!?।])\s+',story) if x.strip()]
    if not parts: parts=["A cheerful adventure begins."]
    beats=["opening","adventure starts","funny problem","first attempt","unexpected twist",
           "clue discovered","teamwork","big funny moment","problem solved","happy ending"]
    char_text="; ".join(f"{c['name']}: {c['look']}" for c in chars)
    scenes=[]
    for i in range(n):
        line=parts[i%len(parts)]
        scenes.append({
          "scene":i+1,"duration":6,
          "prompt":f"3D family cartoon animation. Fixed characters: {char_text}. "
                    f"Action: {line}. Story beat: {beats[i%10]}. "
                    "Keep identical face, hair, body proportions, clothes and colors. "
                    "Cinematic camera, expressive faces, family friendly, no text, no watermark."
        })
    return scenes

st.title("🎬 CartoonFlow AI")
st.caption("Android-first control dashboard • 4-minute cartoon production queue")

with st.sidebar:
    st.header("Project")
    lang=st.selectbox("Language",["Hindi","English","Hinglish"])
    fmt=st.selectbox("Format",["16:9 YouTube","9:16 Shorts"])
    minutes=st.slider("Video length",3,4,4)
    st.divider()
    st.header("Characters")
    count=st.number_input("Characters",1,6,2)
    chars=[]
    defaults=[
      ("Golu","Hero","7-year-old Indian boy, round friendly face, black hair, yellow T-shirt, blue shorts, red shoes"),
      ("Motu","Friend","cute gray elephant, big expressive eyes, blue scarf, friendly smile"),
    ]
    for i in range(int(count)):
        d=defaults[i] if i<2 else (f"Character {i+1}","Supporting","friendly 3D cartoon character")
        with st.expander(d[0],expanded=i<2):
            name=st.text_input("Name",d[0],key=f"name{i}")
            role=st.text_input("Role",d[1],key=f"role{i}")
            look=st.text_area("Fixed appearance",d[2],key=f"look{i}",height=80)
            chars.append({"name":name,"role":role,"look":look})

story=st.text_area("📝 कहानी",height=170,
"""गोलू और मोटू हाथी गाँव से जंगल की ओर जाते हैं। रास्ते में उन्हें एक चमकता हुआ आम मिलता है। दोनों आम को लेकर मजेदार परेशानी में फँस जाते हैं। आखिर में दोनों मिलकर समस्या हल करते हैं और खुशी-खुशी गाँव लौट आते हैं।""")

c1,c2,c3=st.columns(3)
with c1:
    create=st.button("✨ Create Job",type="primary",use_container_width=True)
with c2:
    demo=st.button("🎭 Demo Story",use_container_width=True)
with c3:
    refresh=st.button("🔄 Refresh Queue",use_container_width=True)

if demo:
    story="गोलू और मोटू हाथी जंगल में रास्ता भूल जाते हैं। उन्हें एक छोटी नदी मिलती है। मोटू पानी में फिसल जाता है और दोनों खूब हँसते हैं। एक चतुर तोता उन्हें सही रास्ता दिखाता है और दोनों खुशी-खुशी गाँव लौटते हैं।"
    st.session_state.story=story
    st.rerun()

if create:
    jobs=load_jobs()
    active=sum(x["status"] in ["Queued","Generating"] for x in jobs)
    if active>=5:
        st.error("Queue में पहले से 5 active jobs हैं.")
    else:
        job={
          "id":str(uuid.uuid4())[:8],
          "created":datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
          "status":"Queued",
          "language":lang,
          "format":"16:9" if fmt.startswith("16") else "9:16",
          "minutes":minutes,
          "story":story,
          "characters":chars,
          "scenes":scene_plan(story,chars,minutes)
        }
        jobs.insert(0,job); save_jobs(jobs)
        st.success(f"Job {job['id']} queue में जोड़ दिया गया.")

st.divider()
st.subheader("📋 Generation Queue")
jobs=load_jobs()
if not jobs:
    st.info("अभी कोई video job नहीं है.")
else:
    for j in jobs:
        with st.container(border=True):
            a,b,c,d=st.columns([1,2,2,1])
            a.write(f"**{j['id']}**")
            b.write(f"{j['minutes']} min • {j['format']}")
            c.write(f"{j['language']} • {j['created']}")
            d.write(f"**{j['status']}**")
            with st.expander("Scenes / production manifest"):
                st.write(f"Characters: {', '.join(x['name'] for x in j['characters'])}")
                st.write(f"Scenes: {len(j['scenes'])}")
                st.download_button("Download job JSON",json.dumps(j,ensure_ascii=False,indent=2),
                                   f"cartoonflow_{j['id']}.json","application/json",key=f"dl{j['id']}")

st.divider()
st.subheader("⚙️ Production backend")
st.markdown("""
**Android phone = control panel.** Actual AI generation runs on a remote GPU/backend.

Recommended adapter chain:
`Character reference → scene image → image-to-video 6s clip → TTS → subtitles/SFX → FFmpeg → MP4`

This app creates the production queue and manifests. It does not pretend that a free Android phone can render unlimited AI video locally.
""")
st.warning("For 4–5 x 4-minute videos/day, connect this dashboard to a GPU backend. Free cloud runtimes do not guarantee that capacity.")
