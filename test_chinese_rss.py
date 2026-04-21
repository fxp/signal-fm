"""
Chinese RSS full demo: 36kr + sspai → GLM scoring → script gen → TTS.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.WARNING)

GLM_API_KEY = os.getenv("GLM_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CHANNEL = {
    "id": "cn-demo",
    "topic": "中文科技资讯：AI、大模型、科技产品、互联网",
    "preference": "优先播报 AI 大模型、科技产品发布、重大融资（>1亿）、行业重要趋势；淡化娱乐和生活类内容",
    "style": "formal",
}

RSS_FEEDS = [
    "https://www.36kr.com/feed",
    "https://sspai.com/feed",
]

SEP = "─" * 58


async def main():
    import redis.asyncio as aioredis
    from backend.ingestion.fetcher import RSSFetcher, URLDedup
    from backend.intelligence.scorer import Scorer
    from backend.intelligence.scriptgen import ScriptGenerator
    from backend.synthesis.tts import TTSRouter

    r = aioredis.from_url(REDIS_URL)
    dedup = URLDedup(r, ttl_days=1)
    fetcher = RSSFetcher()
    scorer = Scorer(GLM_API_KEY)
    gen = ScriptGenerator(GLM_API_KEY)
    tts = TTSRouter()

    print("\n" + "═" * 58)
    print("  SIGNAL FM · 中文 RSS 完整演示")
    print("  36氪 + 少数派 → GLM 评分 → 播报稿 → TTS")
    print("═" * 58)

    # Collect items
    all_items = []
    for feed_url in RSS_FEEDS:
        print(f"\n🌐 抓取: {feed_url.split('/')[2]}")
        async for item in fetcher.fetch(feed_url, CHANNEL["id"]):
            if await dedup.is_seen(item.channel_id, item.url):
                continue
            all_items.append(item)
            if len(all_items) >= 12:
                break
        if len(all_items) >= 12:
            break

    print(f"\n  📥 共抓取 {len(all_items)} 条新内容")

    # Score all items
    print(f"\n🧠 GLM-4-Flash 评分中...")
    scored = []
    for item in all_items[:10]:
        result = await scorer.score(
            title=item.title,
            content=item.content,
            source=item.source,
            channel_topic=CHANNEL["topic"],
            channel_preference=CHANNEL["preference"],
        )
        bar = "█" * (result.total // 10) + "░" * (10 - result.total // 10)
        flag = "✅" if result.qualifies else "  "
        print(f"  {flag} [{bar}] {result.total:3d} {item.title[:48]}")
        if result.qualifies:
            scored.append((item, result))

    print(f"\n  通过评分: {len(scored)}/{min(len(all_items), 10)} 条")

    if not scored:
        print("  ⚠️  无内容通过评分，调低阈值或换 RSS 源")
        await r.aclose()
        return

    # Script gen + TTS for top 3
    top3 = sorted(scored, key=lambda x: -x[1].total)[:3]
    audio_files = []

    print(f"\n🎙  生成播报稿 + TTS 合成（前 3 条）")
    for item, score_result in top3:
        print(f"\n{SEP}")
        print(f"  [{score_result.total}分] {item.title[:52]}")
        print(f"  来源: {item.source} | 理由: {score_result.reason[:60]}")

        script = await gen.generate(
            title=item.title,
            content=item.content,
            source=item.source,
            channel_id=CHANNEL["id"],
            score=score_result.total,
            url=item.url,
            style=CHANNEL["style"],
        )
        if not script:
            print("  ❌ 脚本生成失败")
            continue

        print(f"\n  播报稿 ({len(script.text)}字):")
        # Wrap at 54 chars for readability
        words = script.text
        while words:
            print(f"  {words[:54]}")
            words = words[54:]

        path = await tts.synthesize(script.text)
        if path:
            size_kb = path.stat().st_size // 1024
            print(f"\n  🎵 音频: {path.name[:40]} ({size_kb} KB)")
            audio_files.append((item.title, score_result.total, path))
        else:
            print("  ❌ TTS 失败")

    # Summary
    print(f"\n\n{'═' * 58}")
    print("  演示完成")
    print(f"  RSS 抓取: {len(all_items)} 条  |  通过评分: {len(scored)} 条  |  音频: {len(audio_files)} 条")
    if audio_files:
        print(f"\n  播出队列（按评分排序）:")
        for title, score, path in audio_files:
            print(f"    [{score}分] {title[:50]}")
            print(f"           {path}")
    print("═" * 58 + "\n")

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
