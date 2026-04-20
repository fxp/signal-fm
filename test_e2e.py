"""
End-to-end local test for Signal FM pipeline.
Tests: GLM scoring → script gen → Edge TTS → broadcast queue
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GLM_API_KEY = os.getenv("GLM_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
AUDIO_CACHE_DIR = os.getenv("AUDIO_CACHE_DIR", "/tmp/signal-fm/audio")

SAMPLE_ITEM = {
    "title": "OpenAI 发布 GPT-5，推理能力全面超越 o3",
    "content": (
        "OpenAI 今日正式发布 GPT-5 模型，官方基准测试显示其在数学推理、代码生成、"
        "多模态理解等核心任务上全面超越现有最强模型 o3。GPT-5 支持 200 万 token 上下文窗口，"
        "并首次原生集成实时搜索能力，面向 ChatGPT Plus 用户即刻开放，API 定价每百万 token 15 美元。"
        "OpenAI CEO Sam Altman 表示，这是 AI 发展的重要里程碑。"
    ),
    "source": "The Verge",
    "url": "https://theverge.com/test",
    "channel_id": "test",
}

CHANNEL_CONFIG = {
    "id": "test",
    "topic": "AI 大模型与科技产品进展",
    "preference": "优先播报 GPT/Claude 等大模型突破进展，淡化纯商业融资新闻",
    "style": "formal",
}

SEP = "─" * 60


async def test_scorer():
    from backend.intelligence.scorer import Scorer
    print(f"\n{SEP}")
    print("【Layer 2 · Scorer】GLM-4-Flash 四维评分")
    print(SEP)

    scorer = Scorer(GLM_API_KEY)
    result = await scorer.score(
        title=SAMPLE_ITEM["title"],
        content=SAMPLE_ITEM["content"],
        source=SAMPLE_ITEM["source"],
        channel_topic=CHANNEL_CONFIG["topic"],
        channel_preference=CHANNEL_CONFIG["preference"],
    )
    print(f"  新颖性 (novelty):    {result.novelty}/30")
    print(f"  重要性 (importance): {result.importance}/30")
    print(f"  相关性 (relevance):  {result.relevance}/20")
    print(f"  时效性 (urgency):    {result.urgency}/20")
    print(f"  ─────────────────────")
    print(f"  总分:                {result.total}/100  {'✅ 入队' if result.qualifies else '❌ 丢弃'}")
    print(f"  评分理由: {result.reason}")
    return result


async def test_scriptgen(score: int):
    from backend.intelligence.scriptgen import ScriptGenerator
    print(f"\n{SEP}")
    print("【Layer 2 · ScriptGen】GLM-4 播报稿生成")
    print(SEP)

    gen = ScriptGenerator(GLM_API_KEY)
    script = await gen.generate(
        title=SAMPLE_ITEM["title"],
        content=SAMPLE_ITEM["content"],
        source=SAMPLE_ITEM["source"],
        channel_id=SAMPLE_ITEM["channel_id"],
        score=score,
        url=SAMPLE_ITEM["url"],
        style=CHANNEL_CONFIG["style"],
    )
    if script:
        print(f"  播报稿（{len(script.text)} 字）：")
        print(f"  {script.text}")
    return script


async def test_tts(text: str):
    from backend.synthesis.tts import TTSRouter
    print(f"\n{SEP}")
    print("【Layer 3 · TTS】Edge TTS 音频合成")
    print(SEP)

    router = TTSRouter()
    path = await router.synthesize(text)
    if path and path.exists():
        size_kb = path.stat().st_size // 1024
        print(f"  ✅ 音频已生成: {path}")
        print(f"  文件大小: {size_kb} KB")
        return path
    else:
        print("  ❌ TTS 合成失败")
        return None


async def test_redis_stream():
    import redis.asyncio as aioredis
    print(f"\n{SEP}")
    print("【Layer 1 · Redis】Stream 推送与读取")
    print(SEP)

    r = aioredis.from_url(REDIS_URL)
    try:
        await r.ping()
        print("  ✅ Redis 连接正常")

        # Clean test stream
        await r.delete("signal:test")
        msg_id = await r.xadd("signal:test", {"hello": "signal-fm", "ts": "2026-04-20"})
        print(f"  ✅ 写入 Stream: {msg_id}")

        msgs = await r.xread({"signal:test": "0"}, count=1)
        print(f"  ✅ 读取 Stream: {msgs[0][1][0][1]}")
        await r.delete("signal:test")
        return True
    except Exception as e:
        print(f"  ❌ Redis error: {e}")
        return False
    finally:
        await r.aclose()


async def test_broadcast_queue(audio_path: Path, score: int):
    from backend.broadcast.scheduler import BroadcastScheduler, AudioItem
    import redis.asyncio as aioredis
    print(f"\n{SEP}")
    print("【Layer 4 · Broadcast】优先队列调度")
    print(SEP)

    r = aioredis.from_url(REDIS_URL)
    scheduler = BroadcastScheduler(r)

    item = AudioItem(
        priority=0,
        score=score,
        audio_path=str(audio_path),
        title=SAMPLE_ITEM["title"],
        source=SAMPLE_ITEM["source"],
        channel_id="test",
        url=SAMPLE_ITEM["url"],
        score_reason="测试播出项",
        text="测试",
    )
    scheduler.enqueue(item)
    next_item = scheduler.next_item()
    if next_item and next_item.title == SAMPLE_ITEM["title"]:
        print(f"  ✅ 入队并出队正常")
        print(f"  标题: {next_item.title[:50]}")
        print(f"  评分: {next_item.score} → 优先级: {next_item.priority:.2f}")
    else:
        print("  ❌ 队列调度异常")
    await r.aclose()


async def main():
    print("\n" + "═" * 60)
    print("  SIGNAL FM · 本地端到端测试")
    print("  BigModel GLM-4-Flash + GLM-4 + Edge TTS")
    print("═" * 60)

    # 1. Redis
    redis_ok = await test_redis_stream()
    if not redis_ok:
        print("\n❌ Redis 不可用，终止测试")
        sys.exit(1)

    # 2. Scorer
    score_result = await test_scorer()

    # 3. Script gen
    script = await test_scriptgen(score_result.total)
    if not script:
        print("❌ 脚本生成失败，跳过 TTS")
        sys.exit(1)

    # 4. TTS
    audio_path = await test_tts(script.text)

    # 5. Broadcast queue
    if audio_path:
        await test_broadcast_queue(audio_path, score_result.total)

    print(f"\n{'═' * 60}")
    print("  测试完成 ✅")
    if audio_path:
        print(f"  音频文件: {audio_path}")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
