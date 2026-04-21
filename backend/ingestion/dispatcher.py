"""
Dispatcher: schedules fetchers and pushes new items into Redis Stream.
"""
import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any

import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .fetcher import NewsAPIFetcher, RSSFetcher, RawItem, URLDedup
from .crawler import PlaywrightCrawler, CrawledItem

logger = logging.getLogger(__name__)

STREAM_KEY = "signal:raw"


class Dispatcher:
    def __init__(self, redis_client: redis.Redis, newsapi_key: str = ""):
        self.redis = redis_client
        self.dedup = URLDedup(redis_client)
        self.rss_fetcher = RSSFetcher()
        self.news_fetcher = NewsAPIFetcher(newsapi_key) if newsapi_key else None
        self.crawler = PlaywrightCrawler(headless=True)
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
                next_run_time=datetime.now(),  # run immediately on registration
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
                    next_run_time=datetime.now(),
                )

        for crawl_url in channel.get("crawl_urls", []):
            self.scheduler.add_job(
                self._crawl_site,
                "interval",
                minutes=max(interval_minutes, 30),  # crawl less frequently
                args=[crawl_url, channel_id],
                id=f"crawl:{channel_id}:{crawl_url}",
                replace_existing=True,
                next_run_time=datetime.now(),
            )

    async def _fetch_rss(self, feed_url: str, channel_id: str):
        async for item in self.rss_fetcher.fetch(feed_url, channel_id):
            await self._push(item)

    async def _fetch_news(self, keyword: str, channel_id: str):
        async for item in self.news_fetcher.fetch(keyword, channel_id):
            await self._push(item)

    async def _crawl_site(self, crawl_url: str, channel_id: str):
        async for item in self.crawler.crawl_site(crawl_url, channel_id):
            raw = RawItem(
                url=item.url,
                title=item.title,
                content=item.content,
                source=item.source,
                published_at=item.published_at,
                channel_id=channel_id,
            )
            await self._push(raw)

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

    async def trigger_channel(self, channel: dict) -> int:
        """Immediately run all fetch jobs for a channel. Returns number of jobs triggered."""
        channel_id = channel["id"]
        triggered = 0
        for feed_url in channel.get("rss_feeds", []):
            asyncio.create_task(self._fetch_rss(feed_url, channel_id))
            triggered += 1
        for keyword in channel.get("keywords", []):
            if self.news_fetcher:
                asyncio.create_task(self._fetch_news(keyword, channel_id))
                triggered += 1
        for crawl_url in channel.get("crawl_urls", []):
            asyncio.create_task(self._crawl_site(crawl_url, channel_id))
            triggered += 1
        logger.info(f"[trigger] channel={channel_id}, jobs={triggered}")
        return triggered

    async def start(self):
        self.scheduler.start()
        logger.info("Dispatcher started")

    async def stop(self):
        self.scheduler.shutdown(wait=False)
