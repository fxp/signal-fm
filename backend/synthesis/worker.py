"""
TTS worker: consumes scripts from Redis Stream, synthesizes audio, pushes to broadcast queue.
"""
import asyncio
import json
import logging

import redis.asyncio as redis

from .tts import TTSRouter

logger = logging.getLogger(__name__)

SCRIPT_STREAM = "signal:scripts"
AUDIO_STREAM = "signal:audio"
CONSUMER_GROUP = "synthesis"
CONSUMER_NAME = "tts-worker-1"


class SynthesisWorker:
    def __init__(self, redis_client: redis.Redis, voice: str = "zh-CN-XiaoxiaoNeural"):
        self.redis = redis_client
        self.tts = TTSRouter(voice)
        self._running = False

    async def setup(self):
        try:
            await self.redis.xgroup_create(SCRIPT_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
        except redis.ResponseError:
            pass

    async def run(self):
        await self.setup()
        self._running = True
        logger.info("Synthesis worker started")

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    CONSUMER_GROUP,
                    CONSUMER_NAME,
                    {SCRIPT_STREAM: ">"},
                    count=2,
                    block=2000,
                )
                if not messages:
                    continue

                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        await self._process(msg_id, fields)

            except Exception as e:
                logger.error(f"Synthesis worker error: {e}")
                await asyncio.sleep(1)

    async def _process(self, msg_id: bytes, fields: dict[bytes, bytes]):
        data = {k.decode(): v.decode() for k, v in fields.items()}
        text = data.get("text", "")
        voice_key = data.get("voice", "zh-CN-female")
        self.tts.set_voice(voice_key)

        audio_path = await self.tts.synthesize(text)

        if audio_path:
            await self.redis.xadd(
                AUDIO_STREAM,
                {
                    "audio_path": str(audio_path),
                    "title": data.get("title", ""),
                    "source": data.get("source", ""),
                    "channel_id": data.get("channel_id", ""),
                    "score": data.get("score", "0"),
                    "url": data.get("url", ""),
                    "score_reason": data.get("score_reason", ""),
                    "text": text,
                },
                maxlen=200,
            )
            logger.info(f"[synthesis] audio ready: {data.get('title', '')[:50]}")

        await self.redis.xack(SCRIPT_STREAM, CONSUMER_GROUP, msg_id)

    def stop(self):
        self._running = False
