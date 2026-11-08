import os, json, uuid, sqlite3, asyncio, subprocess, shutil, math, threading, time
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()
BASE=Path(__file__).parent
DATA=BASE/"data"; MEDIA=BASE/"media"; REFS=BASE/"character_refs"
for p in (DATA,MEDIA,REFS): p.mkdir(exist_ok=True)

DB=DATA/"jobs.db"
APP_NAME=os.getenv("APP_NAME","CartoonFlow AI")
FAL_KEY=os.getenv("FAL_KEY","").strip()
IMAGE_MODEL=os.getenv("FAL_IMAGE_MODEL","fal-ai/flux/dev")
VIDEO_MODEL=os.getenv("FAL_I2V_MODEL","kling/v4/image-to-video")

app=FastAPI(title=APP_NAME)
app.mount("/static",StaticFiles(directory=BASE/"static"),name="static")
app.mount("/media",StaticFiles(directory=MEDIA),name="media")
templates=Jinja2Templates(directory=BASE/"templates")

def db():
    c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS jobs(
      id TEXT PRIMARY KEY, created TEXT, status TEXT, language TEXT, format TEXT,
      minutes INTEGER, story TEXT, characters TEXT, ref_path TEXT, video_path TEXT, error TEXT)""")
    c.commit(); return c

def rowjob(r):
    if not r:return None
    d=dict(r); d["characters"]=json.loads(d["characters"] or "[]")
    d["video_url"]=f"/media/{Path(d['video_path']).name}" if d.get("video_path") else None
    return d

def scene_plan(story, chars, minutes):
    n=math.ceil(int(minutes)*60/10)
    parts=[p.strip() for p in story.replace("।",".").split(".") if p.strip()]
    if not parts: parts=[story.strip() or "A cheerful village adventure"]
    fixed="; ".join([f"{c['name']}: {c['look']}" for c in chars])
    scenes=[]
    for i in range(n):
        action=parts[i%len(parts)]
        scenes.append({
          "scene":i+1,"duration":10,
          "prompt":f"High quality stylized 3D animated family cartoon, Indian village setting, cinematic lighting, expressive faces, smooth character animation. Fixed characters: {fixed}. Story action: {action}. Keep the same character identity, clothing and proportions. No text, no watermark."
        })
    return scenes

def save_job(j):
    con=db(); con.execute("""INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
      (j["id"],j["created"],j["status"],j["language"],j["format"],j["minutes"],j["story"],
       json.dumps(j["characters"],ensure_ascii=False),j.get("ref_path"),j.get("video_path"),j.get("error")))
    con.commit(); con.close()

def get_job(jid):
    con=db(); r=con.execute("SELECT * FROM jobs WHERE id=?",(jid,)).fetchone(); con.close(); return rowjob(r)

def all_jobs():
    con=db(); rs=con.execute("SELECT * FROM jobs ORDER BY created DESC").fetchall(); con.close(); return [rowjob(x) for x in rs]

@app.get("/",response_class=HTMLResponse)
async def home(request:Request):
    return templates.TemplateResponse("index.html",{"request":request,"app_name":APP_NAME})

@app.get("/api/jobs")
async def jobs(): return {"jobs":all_jobs()}

@app.post("/api/jobs")
async def create_job(language:str=Form(...),format:str=Form(...),minutes:int=Form(...),story:str=Form(...),
                      characters:str=Form(...),reference:UploadFile|None=File(None)):
    if not story.strip(): raise HTTPException(400,"Story खाली है")
    if minutes<1 or minutes>4: raise HTTPException(400,"Video length 1-4 minutes रखें")
    try: chars=json.loads(characters)
    except: raise HTTPException(400,"Characters JSON गलत है")
    jid=uuid.uuid4().hex[:8]; ref_path=None
    if reference and reference.filename:
        ext=Path(reference.filename).suffix.lower() or ".jpg"
        ref_path=str(REFS/f"{jid}{ext}")
        (REFS/f"{jid}{ext}").write_bytes(await reference.read())
    j={"id":jid,"created":datetime.utcnow().isoformat(),"status":"Queued","language":language,
       "format":format,"minutes":minutes,"story":story,"characters":chars,"ref_path":ref_path,
       "video_path":None,"error":None}
    save_job(j)
    return {"id":jid,"status":"Queued"}

@app.post("/api/jobs/{jid}/render")
async def render(jid:str):
    j=get_job(jid)
    if not j: raise HTTPException(404,"Job नहीं मिला")
    if j["status"]=="Generating": return {"message":"पहले से render हो रहा है"}
    threading.Thread(target=render_job,args=(jid,),daemon=True).start()
    return {"message":"AI rendering शुरू हो गया"}

@app.get("/api/jobs/{jid}")
async def one(jid:str):
    j=get_job(jid)
    if not j: raise HTTPException(404,"Job नहीं मिला")
    return j

def update(jid,**kw):
    j=get_job(jid); j.update(kw); save_job(j)

def ffmpeg_concat(clips,out):
    lst=out.parent/(out.stem+"_list.txt")
    lst.write_text("\n".join([f"file '{p.resolve()}'" for p in clips]),encoding="utf-8")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return out

def make_voice(text,lang,out):
    voice={"Hindi":"hi-IN-SwaraNeural","English":"en-US-JennyNeural","Hinglish":"hi-IN-SwaraNeural"}[lang]
    cmd=["edge-tts","--voice",voice,"--text",text,"--write-media",str(out)]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def add_audio(video,audio,out):
    subprocess.run(["ffmpeg","-y","-i",str(video),"-i",str(audio),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-shortest",str(out)],
                   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def fal_image(prompt, image_size, reference_url=None):
    if not FAL_KEY: raise RuntimeError("FAL_KEY सेट नहीं है")
    import fal_client
    if reference_url:
        res=fal_client.subscribe("fal-ai/flux/dev/image-to-image",arguments={
            "image_url":reference_url,
            "prompt":prompt,
            "strength":0.72,
            "image_size":image_size
        })
    else:
        res=fal_client.subscribe(IMAGE_MODEL,arguments={"prompt":prompt,"image_size":image_size})
    return res["images"][0]["url"]

def fal_i2v(prompt,image_url,duration=10):
    if not FAL_KEY: raise RuntimeError("FAL_KEY सेट नहीं है")
    import fal_client
    args={"prompt":prompt,"start_image_url":image_url,"duration":str(duration)}
    res=fal_client.subscribe(VIDEO_MODEL,arguments=args)
    # Model output formats can vary, so accept common keys.
    if isinstance(res,dict):
        if res.get("video",{}).get("url"): return res["video"]["url"]
        if res.get("video_url"): return res["video_url"]
    raise RuntimeError(f"Video URL नहीं मिला: {res}")

def download_url(url,path):
    import urllib.request
    urllib.request.urlretrieve(url,path)

def render_job(jid):
    try:
        j=get_job(jid); update(jid,status="Generating",error=None)
        if not FAL_KEY: raise RuntimeError("Server में FAL_KEY नहीं है. Render environment में API key जोड़ें.")
        scenes=scene_plan(j["story"],j["characters"],j["minutes"])
        work=MEDIA/jid; work.mkdir(exist_ok=True)
        clips=[]
        previous_image_url=None
        for idx,s in enumerate(scenes,1):
            # First scene is text-to-image. Later scenes use the previous scene
            # as an image-to-image reference to improve character/style continuity.
            image_url=fal_image(
                s["prompt"],
                "landscape_16_9" if j["format"]=="16:9" else "portrait_16_9",
                previous_image_url
            )
            previous_image_url=image_url
            img=work/f"scene_{idx:03d}.jpg"; download_url(image_url,img)
            motion=f"{s['prompt']} Camera movement: gentle cinematic push-in, natural body motion, expressive reactions, smooth 3D animation."
            video_url=fal_i2v(motion,image_url,10)
            clip=work/f"clip_{idx:03d}.mp4"; download_url(video_url,clip); clips.append(clip)
        silent=work/"silent.mp4"; ffmpeg_concat(clips,silent)
        audio=work/"voice.mp3"; make_voice(j["story"],j["language"],audio)
        final=MEDIA/f"{jid}.mp4"; add_audio(silent,audio,final)
        update(jid,status="Complete",video_path=str(final),error=None)
    except Exception as e:
        update(jid,status="Failed",error=str(e))

# Seed DB so the app can start cleanly.
db().close()
