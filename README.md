# CartoonFlow AI v4
Working Android-first Streamlit dashboard + MP4 renderer.

Demo mode: no AI API key; makes a real MP4 with scene cards, camera motion and TTS.
AI mode: uses the current Pollinations API for scene images. Put `POLLINATIONS_API_KEY` in Streamlit Secrets.

Current Pollinations documentation says authenticated API access is required. Provider limits/charges can apply.

The renderer is intentionally modular: the scene animation function can later be replaced by a true image-to-video GPU model.
