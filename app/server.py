"""Polyglot demo server: fan a source out to many languages, live.

Streams the real pipeline over SSE so the browser shows what the sponsor asked to
see — a reactive, multi-provider pipeline: per-language progress as events, work
fanning out under a concurrency cap (so a queue visibly drains = backpressure), and
provider failover happening on camera.

Endpoints:
  GET  /                     the dashboard
  POST /api/start            begin a job; body: {languages, concurrency, max_segments, break_elevenlabs}
  GET  /api/events/<job_id>  SSE stream of job events
  GET  /api/languages        catalogue + coverage for the picker
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
# Load .env locally; in a deployment the keys come from real environment variables,
# so a missing .env is fine (real env vars always win via setdefault either way).
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from flask import Flask, Response, jsonify, request  # noqa: E402

from cast.languages import DEMO_WORLD, coverage, get  # noqa: E402
from cast.localize import localize_language  # noqa: E402
from cast.synthesize import DEFAULT_VOICE, VOICES  # noqa: E402
from cast.transcribe import transcribe  # noqa: E402

SOURCE_AUDIO = ROOT / "work" / "source" / "coleman.wav"
CACHE = ROOT / "work" / "transcript.json"
OUT = ROOT / "work" / "localized"

app = Flask(__name__)
_JOBS: dict[str, "Job"] = {}


class Job:
    def __init__(self, langs, concurrency, max_segments, break_el, voice):
        self.id = uuid.uuid4().hex[:12]
        self.langs = langs
        self.concurrency = concurrency
        self.max_segments = max_segments
        self.break_el = break_el
        self.voice = VOICES.get(voice, VOICES[DEFAULT_VOICE])
        self.q: queue.Queue = queue.Queue()
        self.done = False
        self.cancelled = threading.Event()

    def emit(self, **event):
        self.q.put(event)


def _run_job(job: Job) -> None:
    try:
        transcript, run = transcribe(SOURCE_AUDIO, cache_path=CACHE)
        if job.max_segments:
            transcript.segments = transcript.segments[: job.max_segments]
        job.emit(type="transcript", segments=len(transcript.segments),
                 duration=round(transcript.duration, 1),
                 preview=[s.text for s in transcript.segments[:3]])
        for code in job.langs:
            job.emit(type="queued", language=code, name=get(code).name)

        def one(code: str) -> None:
            # A cancel that arrives before this language starts skips it entirely;
            # a language already in flight finishes (we can't interrupt a provider
            # call cleanly), but no new ones begin.
            if job.cancelled.is_set():
                job.emit(type="skipped", language=code)
                return
            job.emit(type="active", language=code)

            def prog(stage, detail):
                job.emit(type="progress", stage=stage, **detail)

            el_key = "sk_elevenlabs_down_for_demo" if job.break_el else None
            try:
                result = localize_language(
                    transcript, code, voice=job.voice, out_dir=OUT,
                    parent=run, on_progress=prog, elevenlabs_key=el_key,
                )
                job.emit(type="done", language=code, failovers=result.failovers,
                         segments=len(result.segment_texts),
                         audio=f"/api/audio/{code}")
            except Exception as exc:  # keep one language's failure from killing the fan-out
                job.emit(type="error", language=code, message=str(exc)[:200])

        with ThreadPoolExecutor(max_workers=job.concurrency) as ex:
            list(ex.map(one, job.langs))
        job.emit(type="all_done")
    except Exception as exc:
        job.emit(type="fatal", message=str(exc)[:300])
    finally:
        job.done = True
        job.q.put(None)  # sentinel closes the SSE stream


@app.post("/api/start")
def start():
    body = request.get_json(force=True) or {}
    langs = [c for c in body.get("languages", list(DEMO_WORLD)) if c]
    job = Job(
        langs=langs,
        concurrency=int(body.get("concurrency", 3)),
        max_segments=int(body.get("max_segments", 3)),
        break_el=bool(body.get("break_elevenlabs", False)),
        voice=body.get("voice", DEFAULT_VOICE),
    )
    _JOBS[job.id] = job
    threading.Thread(target=_run_job, args=(job,), daemon=True).start()
    return jsonify({"job_id": job.id, "languages": langs, "concurrency": job.concurrency})


@app.post("/api/stop/<job_id>")
def stop(job_id: str):
    job = _JOBS.get(job_id)
    if job:
        job.cancelled.set()
    return jsonify({"stopped": bool(job)})


@app.get("/api/events/<job_id>")
def events(job_id: str):
    job = _JOBS.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404

    def stream():
        # Block only briefly, so a reconnect to an already-finished job returns
        # immediately instead of hanging forever on an empty queue — which used to
        # leak a worker/connection per run and, after ~6, stall audio requests
        # behind the browser's per-origin connection limit (the ~15-20s delay).
        while True:
            try:
                item = job.q.get(timeout=1.0)
            except queue.Empty:
                if job.done:
                    yield "event: close\ndata: {}\n\n"
                    return
                yield ": keep-alive\n\n"  # heartbeat holds the connection open
                continue
            if item is None:
                yield "event: close\ndata: {}\n\n"
                return
            yield f"data: {json.dumps(item)}\n\n"

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/audio/<code>")
def audio(code: str):
    path = OUT / code / f"{code}.mp3"
    if not path.exists():
        return jsonify({"error": "not ready"}), 404
    data = path.read_bytes()
    size = len(data)
    # Honor the browser's Range probe with a real 206 so the <audio> element can
    # start/seek immediately. send_file(conditional=True) didn't emit 206 on this
    # Werkzeug build, so this is done by hand and is version-proof.
    rng = request.headers.get("Range")
    if rng and rng.startswith("bytes="):
        try:
            start_s, _, end_s = rng[6:].partition("-")
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else size - 1
        except ValueError:
            start, end = 0, size - 1
        end = min(end, size - 1)
        chunk = data[start:end + 1]
        resp = Response(chunk, 206, mimetype="audio/mpeg")
        resp.headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        resp.headers["Accept-Ranges"] = "bytes"
        return resp
    resp = Response(data, mimetype="audio/mpeg")
    resp.headers["Accept-Ranges"] = "bytes"
    # Each run overwrites <code>.mp3 at a stable URL, so never let the browser serve a
    # cached previous take (it would play old audio under freshly refetched captions).
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/segments/<code>")
def segments(code: str):
    path = OUT / code / "segments.json"
    if not path.exists():
        return jsonify({"error": "not ready"}), 404
    return Response(path.read_text(encoding="utf-8"), mimetype="application/json")


@app.get("/api/languages")
def languages():
    from cast.languages import WORLD_POPULATION_M

    cov = coverage()  # whole catalogue — the headline reach claim
    return jsonify({
        "demo_world": [{"code": c, "name": get(c).name,
                        "l1_m": get(c).l1_speakers_m, "rtl": get(c).rtl}
                       for c in DEMO_WORLD],
        "coverage": {"languages": cov.languages, "native_billions": cov.native_billions,
                     "native_percent": cov.native_percent},
        "voices": [{"key": k, "label": v.label} for k, v in VOICES.items()],
        "world_population_m": WORLD_POPULATION_M,
    })


@app.get("/")
def index():
    return Response((Path(__file__).parent / "index.html").read_text(encoding="utf-8"),
                    mimetype="text/html")


if __name__ == "__main__":
    # Local dev entrypoint. In a container, gunicorn imports `app.server:app` instead
    # (single worker + threads, so the in-memory job state and SSE streams stay put).
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
