import streamlit as st
from pathlib import Path
import json, uuid, datetime

from backend import generate_video

BASE=Path(__file__).parent
DATA=BASE/"data"; OUTPUTS=BASE/"outputs"
DATA.mkdir(exist_ok=True); OUTPUTS.mkdir(exist_ok=True)
JOBS=DATA/"jobs.json"
if not JOBS.exists(): JOBS.write_text("[]", encoding="utf-8")

st.set_page_config(page_title="CartoonFlow AI", page_icon="🎬", layout="wide")

def load_jobs(): return json.loads(JOBS.read_text(encoding="utf-8"))
def save_jobs(j): JOBS.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding="utf-8")

def scene_plan(story, chars, minutes):
    n=minutes*10
    parts=[x.strip() for x in story.replace("।","।|").replace("!","!|").replace("?","?|").split("|") if x.strip()]
    if not parts: parts=["A cheerful village adventure begins.","The characters face a funny problem.","They find a clever solution.","Everyone celebrates happily."]
    ct=", ".join(f"{c['name']} ({c['look']})" for c in chars)
    return [{"scene":i+1,"duration":6,"prompt":f"3D family-friendly cartoon animation, Indian village setting. Characters: {ct}. Action: {parts[i%len(parts)]}. Keep faces, proportions, clothes and colors consistent. Expressive faces, cinematic composition, bright detailed 3D animation."} for i in range(n)]

st.title("🎬 CartoonFlow AI")
st.caption("Android-first 3D cartoon video production dashboard")

with st.sidebar:
    st.header("Project")
    lang=st.selectbox("Language",["Hindi","English","Hinglish"])
    fmt=st.selectbox("Format",["16:9 YouTube","9:16 Shorts"])
    minutes=st.slider("Video length",3,4,4)
    st.divider(); st.header("Characters")
    count=st.number_input("Characters",1,6,2,1)
    chars=[]
    defaults=[("Golu","Hero","7-year-old Indian boy, round friendly face, black hair, yellow T-shirt, blue shorts, red shoes"),("Motu","Friend","cute gray elephant, big expressive eyes, blue scarf, friendly smile")]
    for i in range(int(count)):
        d=defaults[i] if i<2 else (f"Character {i+1}","Supporting","friendly 3D cartoon character")
        with st.expander(d[0],expanded=i<2):
            name=st.text_input("Name",d[0],key=f"name_{i}")
            role=st.text_input("Role",d[1],key=f"role_{i}")
            look=st.text_area("Fixed appearance",d[2],key=f"look_{i}",height=80)
            chars.append({"name":name,"role":role,"look":look})

story=st.text_area("📜 कहानी",value="गोलू और मोटू हाथी गांव से जंगल की ओर जाते हैं। रास्ते में उन्हें एक चमकता हुआ आम मिलता है। दोनों आम को लेकर मजेदार परेशानी में फंस जाते हैं। आखिर में दोनों हंसते हुए घर लौट आते हैं।",height=170)

c1,c2,c3=st.columns(3)
with c1: create=st.button("✨ Create Job",type="primary",use_container_width=True)
with c2: demo=st.button("🎭 Demo Story",use_container_width=True)
with c3: refresh=st.button("🔄 Refresh Queue",use_container_width=True)

if demo:
    st.session_state["story"]="गोलू और मोटू जंगल में रास्ता भूल जाते हैं। उन्हें एक छोटी नदी मिलती है। दोनों मजेदार तरीके से नदी पार करने की कोशिश करते हैं। आखिर में उन्हें सही रास्ता मिल जाता है और दोनों खुशी से घर लौटते हैं।"
    st.rerun()
if "story" in st.session_state: story=st.session_state["story"]

if create:
    jobs=load_jobs()
    active=sum(1 for x in jobs if x.get("status") in ["Queued","Generating"])
    if active>=5: st.error("Queue में पहले से 5 active jobs हैं।")
    else:
        job={"id":str(uuid.uuid4())[:8],"created":datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"status":"Queued","language":lang,"format":"16:9" if fmt.startswith("16") else "9:16","minutes":int(minutes),"story":story,"characters":chars,"scenes":scene_plan(story,chars,int(minutes))}
        jobs.insert(0,job); save_jobs(jobs)
        st.success(f"Job {job['id']} queue में जोड़ दिया गया।")
        st.divider(); st.subheader("🚀 Render Video")
        mode=st.radio("Rendering mode",["Demo render (no API key)","AI images + motion"],horizontal=True)
        if mode.startswith("AI"): st.warning("AI mode के लिए POLLINATIONS_API_KEY को Streamlit Secrets में रखना होगा। Provider limits/charges लागू हो सकते हैं।")
        if st.button("🎬 Start Rendering",type="primary",use_container_width=True):
            jobs=load_jobs()
            for x in jobs:
                if x["id"]==job["id"]: x["status"]="Generating"
            save_jobs(jobs)
            p=st.progress(0); msg=st.empty()
            try:
                out=generate_video(job,"ai" if mode.startswith("AI") else "demo",lambda a,b:(p.progress(min(100,max(0,int(a)))),msg.write(b)))
                jobs=load_jobs()
                for x in jobs:
                    if x["id"]==job["id"]: x["status"]="Complete"; x["output"]=str(out)
                save_jobs(jobs)
                st.success("वीडियो तैयार है।")
                st.download_button("⬇️ Download MP4",Path(out).read_bytes(),file_name=Path(out).name,mime="video/mp4",use_container_width=True)
            except Exception as e:
                jobs=load_jobs()
                for x in jobs:
                    if x["id"]==job["id"]: x["status"]="Failed"; x["error"]=str(e)
                save_jobs(jobs); st.error(f"Rendering failed: {e}")

st.divider(); st.subheader("🎞️ Generation Queue")
jobs=load_jobs()
if not jobs: st.info("अभी कोई video job नहीं है।")
for j in jobs:
    with st.container(border=True):
        a,b,c=st.columns([1,2,2])
        with a: st.write(f"**Job:** {j['id']}")
        with b: st.write(f"**Length:** {j['minutes']} min")
        with c: st.write(f"**Format:** {j['format']}")
        st.write(f"**Language:** {j['language']}  |  **Status:** {j['status']}")
        if j.get("error"): st.error(j["error"])
        if j.get("output") and Path(j["output"]).exists():
            st.download_button("⬇️ Download",Path(j["output"]).read_bytes(),file_name=Path(j["output"]).name,mime="video/mp4",key=f"dl_{j['id']}")
        with st.expander("🎬 Scenes / Production Manifest"):
            st.write("Characters: "+", ".join(x["name"] for x in j["characters"]))
            st.write(f"Scenes: {len(j['scenes'])}")
            st.download_button("⬇️ Download Job JSON",json.dumps(j,ensure_ascii=False,indent=2),file_name=f"cartoonflow_{j['id']}.json",mime="application/json",key=f"json_{j['id']}")

st.divider(); st.subheader("⚙️ Production Backend")
st.markdown("Android phone = control panel\n\nStory → scene images → 6-second motion clips → TTS → MP4")
st.warning("Demo mode real MP4 बनाता है। AI mode external provider/API पर निर्भर है।")
