"""
Integration test: fetch real RSS → push to Redis Stream → run intelligence worker → synthesize.
Runs the full pipeline end-to-end with a real RSS feed.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

GLM_API_KEY = os.getenv("GLM_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CHANNEL = {
    "id": "ai-test",
    "name": "AI 速报",
    "topic": "AI 大模型与科技产品最新进展",
    "preference": "优先播报 GPT、Claude、Gemini 等大模型的突破进展，淡化纯商业融资新闻",
    "style": "formal",
    "interval_minutes": 30,
}

RSS_FEEDS = [
    "https://www.artificialintelligence-news.com/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
]


async def main():
    import redis.asyncio as aioredis
    from backend.ingestion.fetcher import RSSFetcher, URLDedup
    from backend.intelligence.scorer import Scorer
    from backend.intelligence.scriptgen import ScriptGenerator
    from backend.synthesis.tts import TTSRouter

    r = aioredis.from_url(REDIS_URL)
    dedup = URLDedup(r)
    fetcher = RSSFetcher()
    scorer = Scorer(GLM_API_KEY)
    gen = ScriptGenerator(GLM_API_KEY)
    tts = TTSRouter()

    print("\n" + "═" * 60)
    print("  SIGNAL FM · 真实 RSS 全链路测试")
    print("═" * 60)

    # Step 1: Fetch RSS
    items = []
    for feed_url in RSS_FEEDS:
        print(f"\n🌐 抓取 RSS: {feed_url}")
        async for item in fetcher.fetch(feed_url, CHANNEL["id"]):
            if not await dedup.is_seen(item.channel_id, item.url):
                items.append(item)
                if len(items) >= 10:
                    break
        if len(items) >= 10:
            break

    print(f"\n📥 抓取到 {len(items)} 条新内容（去重后）")

    # Step 2: Score + generate for top results
    produced = []
    for item in items[:8]:  # process up to 8 items
        print(f"\n  {'─' * 56}")
        print(f"  📰 {item.title[:70]}")
        print(f"     来源: {item.source}")

        score = await scorer.score(
            title=item.title,
            content=item.content,
            source=item.source,
            channel_topic=CHANNEL["topic"],
            channel_preference=CHANNEL["preference"],
        )
        bar = "█" * (score.total // 10) + "░" * (10 - score.total // 10)
        qualifier = "✅ 入队" if score.qualifies else "❌ 丢弃"
        print(f"     评分: [{bar}] {score.total}/100  {qualifier}")
        print(f"     理由: {score.reason[:80]}")

        if score.qualifies:
            script = await gen.generate(
                title=item.title,
                content=item.content,
                source=item.source,
                channel_id=CHANNEL["id"],
                score=score.total,
                url=item.url,
                style=CHANNEL["style"],
            )
            if script:
                print(f"\n  🎙  播报稿：")
                print(f"  {script.text[:200]}")
                produced.append((script, score.total))

    # Step 3: TTS for top-scored items
    print(f"\n\n{'═' * 60}")
    print(f"  📡 TTS 合成（共 {len(produced)} 条入队）")
    print("═" * 60)

    audio_files = []
    for script, score in sorted(produced, key=lambda x: -x[1])[:3]:
        print(f"\n  🎙  [{score}分] {script.title[:60]}")
        path = await tts.synthesize(script.text)
        if path:
            size_kb = path.stat().st_size // 1024
            print(f"  ✅ 音频: {path.name} ({size_kb} KB)")
            audio_files.append((script, path, score))
        else:
            print(f"  ❌ TTS 失败")

    # Summary
    print(f"\n\n{'═' * 60}")
    print("  测试摘要")
    print("═" * 60)
    print(f"  RSS 抓取: {len(items)} 条")
    print(f"  通过评分 (≥70): {len(produced)} 条")
    print(f"  TTS 合成成功: {len(audio_files)} 条")
    if audio_files:
        top = audio_files[0]
        print(f"\n  最高分播报: [{top[2]}分] {top[0].title[:60]}")
        print(f"  音频路径: {top[1]}")
    print("═" * 60 + "\n")

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
