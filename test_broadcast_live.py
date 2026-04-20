"""
Live broadcast scheduler test: push audio items into the scheduler,
run ingest+play loops, verify WebSocket metadata is pushed.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.WARNING)  # suppress noise

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
AUDIO_DIR = Path(os.getenv("AUDIO_CACHE_DIR", "/tmp/signal-fm/audio"))

ITEMS = [
    {"score": 75, "title": "SAP 将智能 AI 引入人力资源管理"},
    {"score": 93, "title": "OpenAI Agents SDK 推出沙盒执行功能"},
    {"score": 89, "title": "斯坦福 AI 报告：美中 AI 差距正在缩小"},
]


async def subscriber(scheduler, expected_count: int, timeout: int = 30):
    """Listen for WebSocket metadata events from the scheduler."""
    q = scheduler.subscribe()
    received = []
    try:
        for _ in range(expected_count + 5):
            try:
                meta = await asyncio.wait_for(q.get(), timeout=timeout)
                received.append(meta)
                status = meta.get("status")
                title = meta.get("title", "")[:45]
                score = meta.get("score", "")
                audio_url = meta.get("audio_url", "")
                if status == "playing":
                    print(f"  📡 WS: [{score}分] {title}")
                    print(f"       audio_url: {audio_url}")
                else:
                    print(f"  📡 WS: idle")
                if len([r for r in received if r.get("status") == "playing"]) >= expected_count:
                    break
            except asyncio.TimeoutError:
                break
    finally:
        scheduler.unsubscribe(q)
    return received


async def main():
    import redis.asyncio as aioredis
    from backend.broadcast.scheduler import BroadcastScheduler, AudioItem
    import time

    r = aioredis.from_url(REDIS_URL)
    await r.delete("signal:audio")

    print("\n" + "═" * 60)
    print("  SIGNAL FM · 广播调度器实时测试")
    print("═" * 60)

    # Find audio files
    mp3s = sorted(AUDIO_DIR.glob("*.mp3"), key=lambda p: p.stat().st_size)
    if not mp3s:
        print("  ❌ 没有找到音频文件，请先运行 test_pipeline.py")
        return

    print(f"\n  找到 {len(mp3s)} 个音频文件")

    # Push audio items into the audio stream
    for i, item in enumerate(ITEMS):
        mp3 = mp3s[i % len(mp3s)]
        await r.xadd("signal:audio", {
            "audio_path": str(mp3),
            "title": item["title"],
            "source": "测试来源",
            "channel_id": "test",
            "score": str(item["score"]),
            "url": "https://example.com",
            "score_reason": f"评分 {item['score']}/100 的测试内容",
            "text": f"这是{item['title']}的播报稿。",
        })
        print(f"  ✅ 推送 [{item['score']}分]: {item['title']}")

    scheduler = BroadcastScheduler(r)

    print(f"\n▶  启动广播调度器（预期播出 {len(ITEMS)} 条）...\n")

    # Run scheduler + subscriber concurrently
    sub_task = asyncio.create_task(subscriber(scheduler, len(ITEMS)))
    sched_task = asyncio.create_task(scheduler.run())

    # Wait for subscriber to finish (all items played)
    try:
        received = await asyncio.wait_for(sub_task, timeout=120)
    except asyncio.TimeoutError:
        received = []
    finally:
        scheduler.stop()
        sched_task.cancel()
        try:
            await sched_task
        except asyncio.CancelledError:
            pass

    # Report
    playing_events = [r for r in received if r.get("status") == "playing"]
    print(f"\n{'═' * 60}")
    print(f"  广播调度器测试结果")
    print(f"  推入: {len(ITEMS)} 条  |  播出: {len(playing_events)} 条")
    if playing_events:
        scores = [e.get("score", 0) for e in playing_events]
        print(f"  播出顺序评分: {scores}")
        if scores == sorted(scores, reverse=True):
            print(f"  ✅ 优先级排序正确（从高到低）")
        print(f"  ✅ audio_url 字段: {'有' if playing_events[0].get('audio_url') else '无'}")
    print("═" * 60 + "\n")

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
