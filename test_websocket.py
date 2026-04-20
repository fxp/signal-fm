"""
Test WebSocket real-time metadata + broadcast scheduler with audio files.
"""
import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
API_BASE = "http://localhost:8000"


async def test_api_endpoints():
    import httpx
    print("\n【API 端点测试】")
    async with httpx.AsyncClient() as client:
        # now-playing
        r = await client.get(f"{API_BASE}/api/now-playing")
        print(f"  GET /api/now-playing → {r.status_code}: {r.text[:80]}")

        # channels
        r = await client.get(f"{API_BASE}/api/channels")
        chs = r.json()
        print(f"  GET /api/channels → {len(chs)} 个频道")

        # queue
        r = await client.get(f"{API_BASE}/api/queue")
        print(f"  GET /api/queue → {r.status_code}: {r.text[:80]}")


async def test_websocket_client():
    """Connect to WebSocket, push a mock item, receive metadata."""
    import websockets
    print("\n【WebSocket 实时元数据测试】")
    try:
        async with websockets.connect("ws://localhost:8000/ws", open_timeout=5) as ws:
            print("  ✅ WebSocket 连接成功")
            # Wait for one message (up to 5s)
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                print(f"  📡 收到元数据: status={data.get('status')}")
            except asyncio.TimeoutError:
                print("  ℹ️  5s 内无新消息（广播空闲中）")
    except Exception as e:
        print(f"  ❌ WebSocket 连接失败: {e}")


async def test_broadcast_with_real_audio():
    """Push audio items into Audio Stream and verify broadcast scheduler picks them up."""
    import redis.asyncio as aioredis
    from backend.broadcast.scheduler import BroadcastScheduler, AudioItem

    print("\n【广播调度器测试】")
    r = aioredis.from_url(REDIS_URL)

    # Find existing audio files
    audio_dir = Path(os.getenv("AUDIO_CACHE_DIR", "/tmp/signal-fm/audio"))
    mp3_files = sorted(audio_dir.glob("*.mp3"), key=lambda p: p.stat().st_size, reverse=True)[:3]

    if not mp3_files:
        print("  ℹ️  没有找到音频文件，跳过广播测试")
        await r.aclose()
        return

    # Clean audio stream
    await r.delete("signal:audio")

    print(f"  找到 {len(mp3_files)} 个音频文件")
    scheduler = BroadcastScheduler(r)

    # Enqueue items with different scores to test priority
    test_cases = [
        (mp3_files[0], 75, "低优先级测试播报"),
        (mp3_files[min(1, len(mp3_files)-1)], 92, "🔴 突发高分播报（应优先）"),
        (mp3_files[min(2, len(mp3_files)-1)], 83, "中优先级播报"),
    ]

    for path, score, title in test_cases:
        item = AudioItem(
            priority=0,
            score=score,
            audio_path=str(path),
            title=title,
            source="测试来源",
            channel_id="test",
            url="https://example.com",
            score_reason=f"测试评分 {score}",
            text="测试文本",
        )
        scheduler.enqueue(item)
        print(f"  ➕ 入队 [{score}分]: {title}")

    print(f"\n  按优先级出队顺序：")
    order = []
    while True:
        item = scheduler.next_item()
        if not item:
            break
        order.append(item)
        print(f"    [{item.score}分] {item.title}")

    if order[0].score == 92:
        print(f"\n  ✅ 优先级正确：最高分 92 排在首位")
    else:
        print(f"\n  ❌ 优先级错误：{order[0].score} 排首位，期望 92")

    await r.aclose()


async def main():
    print("\n" + "═" * 60)
    print("  SIGNAL FM · API + WebSocket + 广播调度测试")
    print("═" * 60)

    await test_api_endpoints()
    await test_websocket_client()
    await test_broadcast_with_real_audio()

    print(f"\n{'═' * 60}")
    print("  测试完成 ✅")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
