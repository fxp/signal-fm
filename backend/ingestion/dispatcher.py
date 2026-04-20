"""
Dispatcher: schedules fetchers and pushes new items into Redis Stream.
"""
import json
import logging
from dataclasses import asdict
from typing import Any

import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .fetcher import NewsAPIFetcher, RSSFetcher, RawItem, URLDedup

logger = logging.getLogger(__name__)

STREAM_KEY = "signal:raw"


class Dispatcher:
    def __init__(self, redis_client: redis.Redis, newsapi_key: str = ""):
        self.redis = redis_client
        self.dedup = URLDedup(redis_client)
        self.rss_fetcher = RSSFetcher()
        self.news_fetcher = NewsAPIFetcher(newsapi_key) if newsapi_key else None
        self.scheduler = AsyncIOScheduler()

    def register_channel(self, channel: dict[str, Any]):
        """Register a channel's data sources for periodic fetching."""
        channel_id = channel["id"]
        interval_minutes = channel.get("interval_minutes", 15)

        for feed_url in channel.get("rss_feeds", []):
            self.scheduler.add_job(
                self._fetch_rss,
                "interval",
                minutes=interval_minutes,
                args=[feed_url, channel_id],
                id=f"rss:{channel_id}:{feed_url}",
                replace_existing=True,
            )

        for keyword in channel.get("keywords", []):
            if self.news_fetcher:
                self.scheduler.add_job(
                    self._fetch_news,
                    "interval",
                    minutes=interval_minutes,
                    args=[keyword, channel_id],
                    id=f"news:{channel_id}:{keyword}",
                    replace_existing=True,
                )

    async def _fetch_rss(self, feed_url: str, channel_id: str):
        async for item in self.rss_fetcher.fetch(feed_url, channel_id):
            await self._push(item)

    async def _fetch_news(self, keyword: str, channel_id: str):
        async for item in self.news_fetcher.fetch(keyword, channel_id):
            await self._push(item)

    async def _push(self, item: RawItem):
        if not item.url or not item.title:
            return
        if await self.dedup.is_seen(item.channel_id, item.url):
            return

        payload = {
            "url": item.url,
            "title": item.title,
            "content": item.content[:2000],  # cap to avoid oversized payloads
            "source": item.source,
            "published_at": item.published_at.isoformat(),
            "channel_id": item.channel_id,
        }
        await self.redis.xadd(STREAM_KEY, payload, maxlen=1000)
        logger.info(f"[dispatch] pushed: {item.title[:60]}")

    async def start(self):
        self.scheduler.start()
        logger.info("Dispatcher started")

    async def stop(self):
        self.scheduler.shutdown(wait=False)
