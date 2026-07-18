# Cast: transcribe, translate, speak (with failover), assemble, store in B2.
# Single always-on instance: the job state and SSE streams live in-process, so run
# ONE gunicorn worker with threads (never scale to multiple workers/instances or the
# in-memory _JOBS dict and open SSE connections break).

FROM python:3.12-slim

# ffmpeg is required for the assemble/mux stage.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (better layer caching), then the app.
COPY pyproject.toml README.md ./
COPY src ./src
COPY app ./app
COPY scripts ./scripts
# Demo source + its cached transcript, so a cold start has something to localize
# without re-transcribing. (The rest of work/ is generated at runtime.)
COPY work/source ./work/source
COPY work/transcript.json ./work/transcript.json
# A cloned "your voice" preset, if one has been created (optional).
COPY custom_voices.jso[n] ./

RUN pip install --no-cache-dir .

# Platforms (Cloud Run, Render, Railway) inject PORT. Keys come from env vars, not
# a .env file. One worker, generous threads for concurrent SSE + localization.
ENV PORT=8080
EXPOSE 8080
CMD exec gunicorn --workers 1 --threads 24 --timeout 0 \
    --bind "0.0.0.0:${PORT}" app.server:app
