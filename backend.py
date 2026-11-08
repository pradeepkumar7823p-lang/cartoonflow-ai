from pathlib import Path
import os, io, urllib.parse, subprocess, tempfile, asyncio
import requests
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT=Path(__file__).parent; OUT=ROOT/"outputs"; OUT.mkdir(exist_ok=True)
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()

def font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"]:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def placeholder(prompt,size):
    im=Image.new("RGB",size,(245,238,210)); d=ImageDraw.Draw(im)
    d.text((60,60),"CartoonFlow AI",font=font(42),fill=(30,30,30))
    import textwrap
    d.text((60,140),"\n".join(textwrap.wrap(prompt,55)[:10]),font=font(24),fill=(55,55,55))
    return im

def ai_image(prompt,size):
    key=os.environ.get("POLLINATIONS_API_KEY","").strip()
    if not key: raise RuntimeError("POLLINATIONS_API_KEY नहीं मिला। Demo render चुनें या Streamlit Secrets में key जोड़ें।")
    model=os.environ.get("POLLINATIONS_IMAGE_MODEL","black-forest-labs/flux.1-schnell")
    url="https://gen.pollinations.ai/image/"+urllib.parse.quote(prompt,safe="")
    r=requests.get(url,params={"model":model,"width":size[0],"height":size[1]},headers={"Authorization":f"Bearer {key}"},timeout=90)
    r.raise_for_status(); return Image.open(io.BytesIO(r.content)).convert("RGB")

def scene_clip(img,out,seconds,size):
    fps=24; frames=int(seconds*fps)
    vf=f"scale={size[0]}:{size[1]},zoompan=z='min(zoom+0.0008,1.08)':d={frames}:s={size[0]}x{size[1]}:fps={fps}"
    subprocess.run([FFMPEG,"-y","-loop","1","-i",str(img),"-t",str(seconds),"-vf",vf,"-r",str(fps),"-pix_fmt","yuv420p","-an",str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)

def tts(text,lang,out):
    import edge_tts
    voice={"Hindi":"hi-IN-SwaraNeural","English":"en-US-AvaNeural","Hinglish":"hi-IN-SwaraNeural"}.get(lang,"hi-IN-SwaraNeural")
    async def go(): await edge_tts.Communicate(text,voice=voice).save(str(out))
    asyncio.run(go())

def concat(clips,out,audio):
    with tempfile.NamedTemporaryFile("w",suffix=".txt",delete=False,encoding="utf-8") as f:
        for c in clips: f.write("file '"+str(Path(c).resolve())+"'\n")
        lf=f.name
    subprocess.run([FFMPEG,"-y","-f","concat","-safe","0","-i",lf,"-i",str(audio),"-c:v","libx264","-c:a","aac","-shortest","-pix_fmt","yuv420p",str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    Path(lf).unlink(missing_ok=True)

def generate_video(job,mode="demo",progress_callback=None):
    size=(1280,720) if job["format"]=="16:9" else (720,1280)
    work=OUT/job["id"]; work.mkdir(parents=True,exist_ok=True); clips=[]
    scenes=job["scenes"]
    for i,s in enumerate(scenes):
        if progress_callback: progress_callback(i/max(1,len(scenes))*80,f"Scene {i+1}/{len(scenes)} बन रहा है...")
        img=work/f"scene_{i+1:03d}.jpg"
        (ai_image(s["prompt"],size) if mode=="ai" else placeholder(s["prompt"],size)).save(img,quality=90)
        clip=work/f"clip_{i+1:03d}.mp4"; scene_clip(img,clip,s.get("duration",6),size); clips.append(clip)
    if progress_callback: progress_callback(85,"Voice तैयार हो रही है...")
    audio=work/"voice.mp3"; tts(job["story"],job["language"],audio)
    if progress_callback: progress_callback(95,"Final MP4 assemble हो रहा है...")
    out=OUT/f"CartoonFlow_{job['id']}.mp4"; concat(clips,out,audio)
    if progress_callback: progress_callback(100,"Complete")
    return out
