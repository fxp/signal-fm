"""
Broadcast engine: priority queue scheduler with breaking-news interrupt support.
Consumes audio items from Redis Stream, plays them in score×freshness order.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import redis.asyncio as redis

logger = logging.getLogger(__name__)

AUDIO_STREAM = "signal:audio"
CONSUMER_GROUP = "broadcast"
CONSUMER_NAME = "scheduler-1"

BREAKING_NEWS_THRESHOLD = 90  # items scoring above this interrupt current playback


@dataclass(order=True)
class AudioItem:
    priority: float = field(compare=True)  # negative so higher score = higher priority
    score: int = field(compare=False)
    audio_path: str = field(compare=False)
    title: str = field(compare=False)
    source: str = field(compare=False)
    channel_id: str = field(compare=False)
    url: str = field(compare=False)
    score_reason: str = field(compare=False)
    text: str = field(compare=False)
    enqueued_at: float = field(compare=False, default_factory=time.time)


class BroadcastScheduler:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._queue: list[AudioItem] = []
        self._current: AudioItem | None = None
        self._interrupt = asyncio.Event()
        self._running = False
        self._listeners: list[asyncio.Queue] = []  # WebSocket metadata subscribers
        self._history: list[dict] = []  # last 50 played items

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._listeners.remove(q)

    async def _broadcast_meta(self, item: AudioItem | None):
        if item is None:
            meta = {"status": "idle"}
        else:
            audio_filename = Path(item.audio_path).name if item.audio_path else ""
            meta = {
                "status": "playing",
                "title": item.title,
                "source": item.source,
                "score": item.score,
                "score_reason": item.score_reason,
                "url": item.url,
                "channel_id": item.channel_id,
                "audio_url": f"/api/audio/{audio_filename}" if audio_filename else "",
            }
        for q in list(self._listeners):
            try:
                q.put_nowait(meta)
            except asyncio.QueueFull:
                pass

    def _compute_priority(self, score: int, enqueued_at: float) -> float:
        # Freshness decay: items lose 1 priority point per 10 minutes
        age_minutes = (time.time() - enqueued_at) / 60
        effective_score = score - (age_minutes / 10)
        return -effective_score  # negative: lower number = higher priority in heapq

    def enqueue(self, item: AudioItem):
        import heapq
        item.priority = self._compute_priority(item.score, item.enqueued_at)
        heapq.heappush(self._queue, item)
        logger.info(f"[queue] enqueued (score={item.score}): {item.title[:50]}")

        # Breaking news: interrupt current low-priority playback
        if item.score >= BREAKING_NEWS_THRESHOLD:
            if self._current and self._current.score < BREAKING_NEWS_THRESHOLD:
                logger.info(f"[queue] BREAKING NEWS interrupt: {item.title[:50]}")
                self._interrupt.set()

    def next_item(self) -> AudioItem | None:
        import heapq
        if self._queue:
            return heapq.heappop(self._queue)
        return None

    async def setup(self):
        try:
            await self.redis.xgroup_create(AUDIO_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
        except redis.ResponseError:
            pass

    async def ingest_loop(self):
        """Background task: pull audio items from Redis Stream into local priority queue."""
        await self.setup()
        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    CONSUMER_GROUP,
                    CONSUMER_NAME,
                    {AUDIO_STREAM: ">"},
                    count=10,
                    block=2000,
                )
                if not messages:
                    continue
                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        data = {k.decode(): v.decode() for k, v in fields.items()}
                        item = AudioItem(
                            priority=0,
                            score=int(data.get("score", 0)),
                            audio_path=data.get("audio_path", ""),
                            title=data.get("title", ""),
                            source=data.get("source", ""),
                            channel_id=data.get("channel_id", ""),
                            url=data.get("url", ""),
                            score_reason=data.get("score_reason", ""),
                            text=data.get("text", ""),
                        )
                        self.enqueue(item)
                        await self.redis.xack(AUDIO_STREAM, CONSUMER_GROUP, msg_id)
            except Exception as e:
                logger.error(f"Ingest loop error: {e}")
                await asyncio.sleep(1)

    async def play_loop(self):
        """Background task: play items sequentially, respecting interrupts."""
        while self._running:
            item = self.next_item()
            if not item:
                await self._broadcast_meta(None)
                await asyncio.sleep(2)
                continue

            self._current = item
            self._interrupt.clear()
            await self._broadcast_meta(item)

            audio_path = Path(item.audio_path)
            if not audio_path.exists():
                logger.warning(f"[broadcast] audio file missing: {audio_path}")
                self._current = None
                continue

            duration = await self._get_duration(audio_path)
            logger.info(f"[broadcast] playing ({duration:.1f}s): {item.title[:50]}")

            # Simulate playback with interrupt support
            interrupted = False
            try:
                await asyncio.wait_for(self._interrupt.wait(), timeout=duration)
                interrupted = True
            except asyncio.TimeoutError:
                pass  # finished normally

            # Record in history (keep last 50)
            self._history.append({
                "title": item.title,
                "source": item.source,
                "score": item.score,
                "url": item.url,
                "channel_id": item.channel_id,
                "audio_url": f"/api/audio/{audio_path.name}",
            })
            if len(self._history) > 50:
                self._history.pop(0)

            self._current = None

    async def _get_duration(self, path: Path) -> float:
        """Get MP3 duration in seconds using ffprobe."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            import json
            data = json.loads(stdout)
            return float(data["format"]["duration"])
        except Exception:
            return 30.0  # fallback estimate

    async def run(self):
        self._running = True
        await asyncio.gather(self.ingest_loop(), self.play_loop())

    def stop(self):
        self._running = False
