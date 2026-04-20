"""
Intelligence worker: consumes raw items from Redis Stream, scores them,
generates scripts for qualifying items, pushes to audio queue.
"""
import asyncio
import json
import logging
from typing import Any

import redis.asyncio as redis

from .scorer import Scorer
from .scriptgen import ScriptGenerator

logger = logging.getLogger(__name__)

RAW_STREAM = "signal:raw"
SCRIPT_STREAM = "signal:scripts"
CONSUMER_GROUP = "intelligence"
CONSUMER_NAME = "worker-1"


class IntelligenceWorker:
    def __init__(
        self,
        redis_client: redis.Redis,
        glm_api_key: str,
        channels: dict[str, dict],  # channel_id -> channel config
    ):
        self.redis = redis_client
        self.scorer = Scorer(glm_api_key)
        self.generator = ScriptGenerator(glm_api_key)
        self.channels = channels
        self._running = False

    async def setup(self):
        try:
            await self.redis.xgroup_create(RAW_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
        except redis.ResponseError:
            pass  # group already exists

    async def run(self):
        await self.setup()
        self._running = True
        logger.info("Intelligence worker started")

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    CONSUMER_GROUP,
                    CONSUMER_NAME,
                    {RAW_STREAM: ">"},
                    count=5,
                    block=2000,
                )
                if not messages:
                    continue

                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        await self._process(msg_id, fields)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)

    async def _process(self, msg_id: bytes, fields: dict[bytes, bytes]):
        data = {k.decode(): v.decode() for k, v in fields.items()}
        channel_id = data.get("channel_id", "")
        channel = self.channels.get(channel_id, {})

        score_result = await self.scorer.score(
            title=data.get("title", ""),
            content=data.get("content", ""),
            source=data.get("source", ""),
            channel_topic=channel.get("topic", "科技资讯"),
            channel_preference=channel.get("preference", ""),
        )

        title = data.get("title", "")[:60]
        logger.info(f"[score] {score_result.total}/100 — {title}")

        if not score_result.qualifies:
            await self.redis.xack(RAW_STREAM, CONSUMER_GROUP, msg_id)
            return

        script = await self.generator.generate(
            title=data.get("title", ""),
            content=data.get("content", ""),
            source=data.get("source", ""),
            channel_id=channel_id,
            score=score_result.total,
            url=data.get("url", ""),
            style=channel.get("style", "formal"),
        )

        if script:
            await self.redis.xadd(
                SCRIPT_STREAM,
                {
                    "text": script.text,
                    "title": script.title,
                    "source": script.source,
                    "channel_id": script.channel_id,
                    "score": str(script.score),
                    "url": script.url,
                    "score_reason": score_result.reason,
                },
                maxlen=500,
            )
            logger.info(f"[script] queued (score={score_result.total}): {title}")

        await self.redis.xack(RAW_STREAM, CONSUMER_GROUP, msg_id)

    def stop(self):
        self._running = False
