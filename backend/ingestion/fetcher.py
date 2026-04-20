"""
Data ingestion layer: RSS feeds, NewsAPI, and URL deduplication via Redis.
"""
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Generator

import feedparser
import httpx
import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class RawItem:
    url: str
    title: str
    content: str
    source: str
    published_at: datetime
    channel_id: str


class URLDedup:
    """SHA256-based URL deduplication using Redis Set."""

    def __init__(self, redis_client: redis.Redis, ttl_days: int = 7):
        self.redis = redis_client
        self.ttl = ttl_days * 86400

    def _key(self, channel_id: str) -> str:
        return f"dedup:{channel_id}"

    async def is_seen(self, channel_id: str, url: str) -> bool:
        h = hashlib.sha256(url.encode()).hexdigest()
        key = self._key(channel_id)
        added = await self.redis.sadd(key, h)
        if added:
            await self.redis.expire(key, self.ttl)
            return False
        return True


class RSSFetcher:
    """Fetch and parse RSS feeds."""

    async def fetch(self, feed_url: str, channel_id: str) -> Generator[RawItem, None, None]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(feed_url)
                resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except Exception as e:
            logger.warning(f"RSS fetch failed for {feed_url}: {e}")
            return

        for entry in feed.entries:
            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "content"):
                content = entry.content[0].value if entry.content else ""

            published_at = datetime.now()
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6])

            yield RawItem(
                url=entry.get("link", ""),
                title=entry.get("title", ""),
                content=content,
                source=feed.feed.get("title", feed_url),
                published_at=published_at,
                channel_id=channel_id,
            )


class NewsAPIFetcher:
    """Fetch from NewsAPI.org."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/everything"

    async def fetch(self, query: str, channel_id: str, page_size: int = 20) -> Generator[RawItem, None, None]:
        params = {
            "q": query,
            "apiKey": self.api_key,
            "pageSize": page_size,
            "sortBy": "publishedAt",
            "language": "zh",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(self.base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning(f"NewsAPI fetch failed for '{query}': {e}")
            return

        for article in data.get("articles", []):
            content = article.get("content") or article.get("description") or ""
            published_at = datetime.now()
            if article.get("publishedAt"):
                try:
                    published_at = datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00"))
                except ValueError:
                    pass

            yield RawItem(
                url=article.get("url", ""),
                title=article.get("title", ""),
                content=content,
                source=article.get("source", {}).get("name", "NewsAPI"),
                published_at=published_at,
                channel_id=channel_id,
            )
