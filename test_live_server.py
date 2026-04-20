"""
Live server test: push items into Redis Stream and wait for the running
FastAPI background workers (intelligence + synthesis) to process them.
"""
import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import httpx

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
API_BASE = "http://localhost:8000"

ITEMS = [
    {
        "url": "https://live-test.com/item1",
        "title": "Meta 发布 Llama 4 系列，开源模型登顶全球排行榜",
        "content": "Meta AI 今日正式发布 Llama 4 系列开源大模型，包含 Scout（170 亿参数）、Maverick（1230 亿参数）"
                   "和 Behemoth 三款产品。官方数据显示，Llama 4 Behemoth 在 MMLU Pro、GPQA 等多个权威基准上"
                   "超越 GPT-5 和 Claude 4 Opus，成为首个在全面基准上击败所有闭源模型的开源产品。"
                   "Meta CEO 扎克伯格称这标志着 AI 开源生态进入新纪元。",
        "source": "科技快报",
        "published_at": datetime.now().isoformat(),
        "channel_id": "2d253a46",
    },
    {
        "url": "https://live-test.com/item2",
        "title": "微软 Copilot+ PC 销量超 2000 万台",
        "content": "微软今日发布财报显示，搭载 NPU 的 Copilot+ PC 全球销量已突破 2000 万台。"
                   "微软称 Windows AI 功能月活用户达 1.5 亿，Copilot 日均对话量超 5 亿次。",
        "source": "华尔街日报",
        "published_at": datetime.now().isoformat(),
        "channel_id": "2d253a46",
    },
]


async def main():
    import redis.asyncio as aioredis

    r = aioredis.from_url(REDIS_URL)

    print("\n" + "═" * 60)
    print("  SIGNAL FM · 活服务器集成测试")
    print("  （推送 → 等 worker 自动处理 → 检查结果）")
    print("═" * 60)

    # Get channel count
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/api/channels")
        chs = resp.json()
        print(f"\n📡 API 服务正常，当前频道: {len(chs)} 个")
        for ch in chs:
            print(f"  [{ch['id']}] {ch['name']}")

    # Count items before
    before_scripts = await r.xlen("signal:scripts")
    before_audio = await r.xlen("signal:audio")
    print(f"\n📊 当前状态: scripts={before_scripts}, audio={before_audio}")

    # Push items
    print(f"\n📤 推送 {len(ITEMS)} 条内容到 Raw Stream...")
    for item in ITEMS:
        mid = await r.xadd("signal:raw", item)
        print(f"  ✅ {mid.decode()} → {item['title'][:55]}")

    # Wait for workers to process
    print(f"\n⏳ 等待后台 worker 处理（最多 60s）...")
    for elapsed in range(60):
        await asyncio.sleep(1)
        cur_scripts = await r.xlen("signal:scripts")
        cur_audio = await r.xlen("signal:audio")
        new_scripts = cur_scripts - before_scripts
        new_audio = cur_audio - before_audio
        print(f"  {elapsed+1:2d}s: +{new_scripts} 播报稿, +{new_audio} 音频", end="\r")
        if new_audio >= 1:
            print(f"\n  ✅ {elapsed+1}s 后检测到新音频！")
            break
    else:
        print(f"\n  ⚠️  60s 内未检测到新音频（worker 可能需要 API key 或未启动）")

    # Show final state
    print(f"\n📊 最终状态:")
    print(f"  scripts: {await r.xlen('signal:scripts')}")
    print(f"  audio:   {await r.xlen('signal:audio')}")

    # Check now-playing via API
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/api/now-playing")
        data = resp.json()
        print(f"\n🎙  Now Playing: {data['status']}")
        if data.get("title"):
            print(f"  标题: {data['title']}")
            print(f"  评分: {data.get('score')}")

        # Queue
        resp = await client.get(f"{API_BASE}/api/queue")
        queue = resp.json()
        print(f"\n📋 播放队列: {len(queue)} 条")
        for item in queue[:5]:
            print(f"  [{item['score']}] {item['title'][:50]}")

    print(f"\n{'═' * 60}")
    print("  活服务器测试完成 ✅")
    print("═" * 60 + "\n")

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
