# CartoonFlow AI v5

Android-first web app for turning a story into short AI-generated cartoon clips and assembling them into an MP4.

## What is real in v5
- FastAPI web backend
- Responsive mobile website
- Story -> scene plan
- Character cards
- Optional character reference upload
- fal.ai image generation
- fal.ai image-to-video generation
- Hindi/English/Hinglish voice-over using edge-tts
- FFmpeg MP4 assembly
- 16:9 YouTube / 9:16 Shorts
- Job status and download

## Important
AI rendering is cloud compute and is not unlimited/free. Keep the API key on the server, never in browser JavaScript.

## Local run
1. Install Python 3.11 and FFmpeg.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`
4. Add your FAL_KEY.
5. `uvicorn app:app --reload`
6. Open http://127.0.0.1:8000

## Deploy
The included `render.yaml` can be used with Render. Set FAL_KEY as a secret environment variable.

## Production upgrade
For a paid public service, replace the in-process worker with Redis/Celery or a managed queue, use object storage for media, and add authentication, quotas and billing.
