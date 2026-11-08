
# CartoonFlow AI Android-first v3

## What this version provides
- Mobile-friendly Streamlit dashboard
- Story input
- Character cards with fixed appearance
- 3–4 minute scene planning (30–40 scenes)
- Up to 5 active jobs in the queue
- 16:9 YouTube / 9:16 Shorts
- Downloadable production manifests

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

For Android use, host this app on a web server and open its URL in Chrome. Add it to the home screen for an app-like experience.

## Important architecture
The phone is only the controller. Actual image-to-video rendering should run on a GPU backend. The queue manifest is designed to connect to:
1. Character reference image storage
2. Image generation
3. Image-to-video generation
4. TTS
5. FFmpeg assembly
6. Object storage
7. Download link

The 5-job queue is a workflow limit, not a promise that five jobs can render simultaneously on free infrastructure.

## Production adapter contract
A backend worker can read `data/jobs.json`, claim a `Queued` job, render all scenes, update status, and save the final MP4 path.

Example states:
Queued -> Generating -> Assembling -> Complete
or
Queued -> Generating -> Failed
