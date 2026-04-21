"""
FastAPI backend: REST API + WebSocket for real-time metadata push.
"""
import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import redis.asyncio as redis_asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..broadcast.scheduler import BroadcastScheduler
from ..ingestion.dispatcher import Dispatcher
from ..intelligence.worker import IntelligenceWorker
from ..synthesis.worker import SynthesisWorker
from .models import ChannelCreate, ChannelResponse, NowPlayingResponse, QueueItem

logger = logging.getLogger(__name__)

# In-memory channel store (replace with DB in production)
_channels: dict[str, dict] = {}
_redis: redis_asyncio.Redis | None = None
_scheduler: BroadcastScheduler | None = None
_dispatcher: Dispatcher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis, _scheduler, _dispatcher

    _redis = redis_asyncio.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"),
        decode_responses=False,
    )

    glm_key = os.getenv("GLM_API_KEY", "")
    newsapi_key = os.getenv("NEWSAPI_KEY", "")

    _dispatcher = Dispatcher(_redis, newsapi_key)
    intelligence_worker = IntelligenceWorker(_redis, glm_key, _channels)
    synthesis_worker = SynthesisWorker(_redis)
    _scheduler = BroadcastScheduler(_redis)

    await _dispatcher.start()

    tasks = [
        asyncio.create_task(intelligence_worker.run()),
        asyncio.create_task(synthesis_worker.run()),
        asyncio.create_task(_scheduler.run()),
    ]

    yield

    _dispatcher and await _dispatcher.stop()
    for t in tasks:
        t.cancel()
    _redis and await _redis.aclose()


app = FastAPI(title="Signal FM API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Channel endpoints ---

@app.post("/api/channels", response_model=ChannelResponse)
async def create_channel(body: ChannelCreate):
    channel_id = str(uuid.uuid4())[:8]
    channel = {
        "id": channel_id,
        **body.model_dump(),
    }
    _channels[channel_id] = channel

    if _dispatcher:
        _dispatcher.register_channel(channel)

    return ChannelResponse(**channel)


@app.get("/api/channels", response_model=list[ChannelResponse])
async def list_channels():
    return [ChannelResponse(**ch) for ch in _channels.values()]


@app.get("/api/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: str):
    ch = _channels.get(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ChannelResponse(**ch)


@app.delete("/api/channels/{channel_id}")
async def delete_channel(channel_id: str):
    if channel_id not in _channels:
        raise HTTPException(status_code=404, detail="Channel not found")
    del _channels[channel_id]
    return {"ok": True}


# --- Playback endpoints ---

@app.get("/api/now-playing", response_model=NowPlayingResponse)
async def now_playing():
    if not _scheduler or not _scheduler._current:
        return NowPlayingResponse(status="idle")
    item = _scheduler._current
    from pathlib import Path
    audio_filename = Path(item.audio_path).name if item.audio_path else ""
    return NowPlayingResponse(
        status="playing",
        title=item.title,
        source=item.source,
        score=item.score,
        score_reason=item.score_reason,
        url=item.url,
        channel_id=item.channel_id,
        audio_url=f"/api/audio/{audio_filename}" if audio_filename else None,
    )


@app.get("/api/queue", response_model=list[QueueItem])
async def get_queue():
    if not _scheduler:
        return []
    return [
        QueueItem(
            title=item.title,
            source=item.source,
            score=item.score,
            channel_id=item.channel_id,
        )
        for item in sorted(_scheduler._queue, key=lambda x: x.priority)[:20]
    ]


@app.post("/api/skip")
async def skip_current():
    """Skip the currently playing item."""
    if not _scheduler or not _scheduler._current:
        return {"ok": False, "reason": "nothing playing"}
    _scheduler._interrupt.set()
    return {"ok": True}


@app.get("/api/history")
async def get_history():
    """Return the last 50 played items."""
    if not _scheduler:
        return []
    return list(reversed(_scheduler._history))


@app.get("/api/audio/{filename}")
async def serve_audio(filename: str):
    audio_dir = Path(os.getenv("AUDIO_CACHE_DIR", "/tmp/signal-fm/audio"))
    path = audio_dir / filename
    if not path.exists() or not path.suffix == ".mp3":
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="audio/mpeg")


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if not _scheduler:
        await websocket.close()
        return

    q = _scheduler.subscribe()
    # Push current state immediately on connect
    if _scheduler._current:
        item = _scheduler._current
        audio_filename = Path(item.audio_path).name if item.audio_path else ""
        await websocket.send_json({
            "status": "playing",
            "title": item.title,
            "source": item.source,
            "score": item.score,
            "score_reason": item.score_reason,
            "url": item.url,
            "channel_id": item.channel_id,
            "audio_url": f"/api/audio/{audio_filename}" if audio_filename else "",
        })
    else:
        await websocket.send_json({"status": "idle"})

    try:
        while True:
            meta = await asyncio.wait_for(q.get(), timeout=30)
            await websocket.send_json(meta)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        _scheduler.unsubscribe(q)


# Serve React frontend in production
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
