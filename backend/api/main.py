"""
FastAPI backend: REST API + WebSocket for real-time metadata push.
"""
import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import redis.asyncio as redis_asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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


@app.post("/api/channels/{channel_id}/trigger")
async def trigger_channel_fetch(channel_id: str):
    """Immediately trigger data fetch for a channel (runs all RSS/crawl jobs now)."""
    ch = _channels.get(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    if not _dispatcher:
        raise HTTPException(status_code=503, detail="Dispatcher not ready")
    count = await _dispatcher.trigger_channel(ch)
    return {"ok": True, "jobs_triggered": count}


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


class AskRequest(BaseModel):
    question: str


@app.post("/api/ask")
async def ask_about_current(body: AskRequest):
    """Stream a GLM-4 answer about the currently playing article."""
    if not _scheduler or not _scheduler._current:
        async def no_content():
            yield "data: 当前没有正在播出的内容，请等待播报开始后再提问。\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_content(), media_type="text/event-stream")

    item = _scheduler._current
    glm_key = os.getenv("GLM_API_KEY", "")
    if not glm_key:
        raise HTTPException(status_code=500, detail="GLM_API_KEY not configured")

    context = f"""标题：{item.title}
来源：{item.source}
原文链接：{item.url}
播报内容：{item.text}"""

    system_prompt = (
        "你是 Signal FM 的智能助理，正在帮助用户深入了解刚才播报的新闻内容。"
        "请基于提供的播报内容回答用户问题，如实回答，不要编造原文中没有的信息。"
        "回答简洁、准确，用中文。"
    )

    async def stream_response() -> AsyncGenerator[str, None]:
        try:
            from zhipuai import ZhipuAI
            import concurrent.futures

            client = ZhipuAI(api_key=glm_key)

            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                response = await loop.run_in_executor(
                    pool,
                    lambda: client.chat.completions.create(
                        model="glm-4-flash",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"关于刚才的播报内容：\n{context}\n\n用户问题：{body.question}"},
                        ],
                        stream=True,
                        temperature=0.5,
                        max_tokens=512,
                    ),
                )

                for chunk in response:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        text = delta.content.replace("\n", "\\n")
                        yield f"data: {text}\n\n"

        except Exception as e:
            logger.error(f"Ask endpoint error: {e}")
            yield f"data: 抱歉，回答时发生错误：{e}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")


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
