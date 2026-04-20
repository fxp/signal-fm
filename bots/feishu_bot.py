"""
Feishu (Lark) Bot: listens to the script stream and pushes text summaries
with score details to a Feishu webhook.
"""
import asyncio
import logging
import os

import httpx
import redis.asyncio as redis

logger = logging.getLogger(__name__)

SCRIPT_STREAM = "signal:scripts"
CONSUMER_GROUP = "feishu-bot"
CONSUMER_NAME = "bot-1"

SCORE_EMOJI = {
    range(90, 101): "🔴",
    range(75, 90): "🟡",
    range(0, 75): "🟢",
}


def _score_emoji(score: int) -> str:
    for r, emoji in SCORE_EMOJI.items():
        if score in r:
            return emoji
    return "⚪"


def _build_card(title: str, source: str, score: int, reason: str, text: str, url: str) -> dict:
    emoji = _score_emoji(score)
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{emoji} {title}"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": text},
                },
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**来源**\n{source}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**评分**\n{score}/100"}},
                    ],
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"*{reason}*"},
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看原文"},
                            "type": "default",
                            "url": url,
                        }
                    ],
                },
            ],
        },
    }


class FeishuBot:
    def __init__(self, redis_client: redis.Redis, webhook_url: str, min_score: int = 80):
        self.redis = redis_client
        self.webhook_url = webhook_url
        self.min_score = min_score
        self._running = False

    async def setup(self):
        try:
            await self.redis.xgroup_create(SCRIPT_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
        except redis.ResponseError:
            pass

    async def _send(self, payload: dict):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[feishu] send failed: {e}")

    async def run(self):
        await self.setup()
        self._running = True
        logger.info("Feishu bot started")

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    CONSUMER_GROUP,
                    CONSUMER_NAME,
                    {SCRIPT_STREAM: ">"},
                    count=5,
                    block=5000,
                )
                if not messages:
                    continue

                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        data = {k.decode(): v.decode() for k, v in fields.items()}
                        score = int(data.get("score", 0))

                        if score >= self.min_score:
                            card = _build_card(
                                title=data.get("title", ""),
                                source=data.get("source", ""),
                                score=score,
                                reason=data.get("score_reason", ""),
                                text=data.get("text", ""),
                                url=data.get("url", "#"),
                            )
                            await self._send(card)
                            logger.info(f"[feishu] pushed (score={score}): {data.get('title', '')[:50]}")

                        await self.redis.xack(SCRIPT_STREAM, CONSUMER_GROUP, msg_id)

            except Exception as e:
                logger.error(f"Feishu bot error: {e}")
                await asyncio.sleep(2)

    def stop(self):
        self._running = False


async def main():
    logging.basicConfig(level=logging.INFO)
    r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    webhook = os.getenv("FEISHU_WEBHOOK_URL", "")
    min_score = int(os.getenv("FEISHU_MIN_SCORE", "80"))

    if not webhook:
        logger.error("FEISHU_WEBHOOK_URL not set")
        return

    bot = FeishuBot(r, webhook, min_score)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
