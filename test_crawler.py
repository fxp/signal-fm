"""
Playwright crawler test: crawl a JS-rendered site and run through scoring pipeline.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")

GLM_API_KEY = os.getenv("GLM_API_KEY", "")

CHANNEL = {
    "id": "crawler-test",
    "topic": "AI 大模型与科技产品最新进展",
    "preference": "优先播报 AI 模型发布、重大技术突破、科技公司战略变化",
}

# Sites without RSS but with AI content
CRAWL_TARGETS = [
    "https://www.aibase.com",       # AI 工具导航，JS 渲染
    "https://venturebeat.com/ai/",  # AI beat，英文
]


async def main():
    from backend.ingestion.crawler import PlaywrightCrawler
    from backend.intelligence.scorer import Scorer

    crawler = PlaywrightCrawler(headless=True)
    scorer = Scorer(GLM_API_KEY)

    print("\n" + "═" * 62)
    print("  SIGNAL FM · Playwright 爬虫测试")
    print("═" * 62)

    all_items = []
    for target_url in CRAWL_TARGETS:
        print(f"\n🌐 爬取: {target_url}")
        count = 0
        async for item in crawler.crawl_site(target_url, CHANNEL["id"], max_articles=4):
            all_items.append(item)
            count += 1
            print(f"  ✅ [{count}] {item.title[:58]}")
            print(f"       内容长度: {len(item.content)} 字符")
        if count == 0:
            print("  ⚠️  未找到文章链接")

    if not all_items:
        print("\n❌ 所有目标网站均爬取失败")
        return

    print(f"\n\n🧠 GLM-4-Flash 评分（共 {len(all_items)} 条）")
    print("─" * 62)

    passed = []
    for item in all_items:
        result = await scorer.score(
            title=item.title,
            content=item.content,
            source=item.source,
            channel_topic=CHANNEL["topic"],
            channel_preference=CHANNEL["preference"],
        )
        bar = "█" * (result.total // 10) + "░" * (10 - result.total // 10)
        flag = "✅ 入队" if result.qualifies else "❌ 过滤"
        print(f"  [{bar}] {result.total:3d} {flag} — {item.title[:45]}")
        if result.qualifies:
            passed.append((item, result))

    print(f"\n{'═' * 62}")
    print(f"  爬取: {len(all_items)} 条  |  通过评分: {len(passed)} 条")
    for item, score in passed[:3]:
        print(f"  ✅ [{score.total}] {item.title[:55]}")
    print("═" * 62 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
