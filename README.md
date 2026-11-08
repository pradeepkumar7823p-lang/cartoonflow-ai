# CartoonFlow AI v6

This is a real web-app starter. Android is only the control device; rendering is done by fal.ai.

Pipeline:
Story -> scene prompts -> AI scene images -> AI image-to-video clips -> Hindi/English TTS -> FFmpeg -> MP4

## Deploy
1. Create a GitHub repository and upload these files.
2. Deploy with the included `render.yaml` or Dockerfile.
3. Add `FAL_KEY` as a server environment secret.
4. Open the generated website on Android.

## Important
A 3-4 minute video is assembled from many short AI clips. Every clip consumes provider compute/credits. This is not unlimited free generation.

Never put FAL_KEY in frontend JavaScript or the browser.
