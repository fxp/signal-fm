"""
Playwright-based web crawler for sites without RSS feeds.
Extracts article lists and content from JS-rendered pages.
"""
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

# CSS selectors for common article list patterns
ARTICLE_LINK_SELECTORS = [
    "article a[href]",
    ".post-title a[href]",
    ".article-title a[href]",
    "h2 a[href]",
    "h3 a[href]",
    ".entry-title a[href]",
    ".item-title a[href]",
    "[class*='title'] a[href]",
]

# Content extraction selectors (in priority order)
CONTENT_SELECTORS = [
    "article",
    "[class*='article-body']",
    "[class*='post-content']",
    "[class*='entry-content']",
    "main",
    ".content",
]


@dataclass
class CrawledItem:
    url: str
    title: str
    content: str
    source: str
    published_at: datetime
    channel_id: str


class PlaywrightCrawler:
    """Headless browser crawler for JS-rendered sites."""

    def __init__(self, headless: bool = True, timeout_ms: int = 15000):
        self.headless = headless
        self.timeout_ms = timeout_ms

    # URL path segments that indicate non-article pages
    _SKIP_PATTERNS = re.compile(
        r"/(author|authors|category|categories|tag|tags|page|topic|topics|search|about|contact|subscribe)(/|$)",
        re.IGNORECASE,
    )

    async def _get_article_links(self, page: Page, base_url: str, max_links: int = 10) -> list[str]:
        """Extract article links from a listing page."""
        links = []
        seen = set()
        for selector in ARTICLE_LINK_SELECTORS:
            elements = await page.query_selector_all(selector)
            for el in elements:
                href = await el.get_attribute("href")
                if not href or href.startswith(("#", "javascript:")):
                    continue
                full_url = urljoin(base_url, href)
                parsed = urlparse(full_url)
                # Skip: different domain, non-article paths, already seen
                if parsed.netloc != urlparse(base_url).netloc:
                    continue
                if self._SKIP_PATTERNS.search(parsed.path):
                    continue
                if full_url in seen:
                    continue
                seen.add(full_url)
                links.append(full_url)
                if len(links) >= max_links:
                    break
            if links:
                break
        return links[:max_links]

    async def _extract_content(self, page: Page, url: str) -> tuple[str, str]:
        """Extract (title, content) from an article page."""
        title = await page.title()
        # Clean up title
        title = re.sub(r"\s*[-–|]\s*.+$", "", title).strip()

        content = ""
        for selector in CONTENT_SELECTORS:
            el = await page.query_selector(selector)
            if el:
                content = await el.inner_text()
                content = re.sub(r"\n{3,}", "\n\n", content).strip()
                if len(content) > 200:
                    break

        return title, content[:3000]

    async def crawl_site(
        self,
        url: str,
        channel_id: str,
        max_articles: int = 5,
    ) -> AsyncGenerator[CrawledItem, None]:
        """
        Crawl a website: open the listing page, follow article links,
        extract content from each article.
        """
        source = urlparse(url).netloc.replace("www.", "")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            try:
                logger.info(f"[crawler] opening: {url}")
                await page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                article_links = await self._get_article_links(page, url, max_articles)
                logger.info(f"[crawler] found {len(article_links)} article links")

                for article_url in article_links:
                    try:
                        await page.goto(article_url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                        await page.wait_for_timeout(1500)

                        title, content = await self._extract_content(page, article_url)
                        if not title or len(content) < 100:
                            continue

                        yield CrawledItem(
                            url=article_url,
                            title=title,
                            content=content,
                            source=source,
                            published_at=datetime.now(),
                            channel_id=channel_id,
                        )
                    except Exception as e:
                        logger.warning(f"[crawler] article error {article_url}: {e}")
                        continue

            except Exception as e:
                logger.error(f"[crawler] site error {url}: {e}")
            finally:
                await browser.close()
