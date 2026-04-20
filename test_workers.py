"""
Worker integration test: push items into Redis Stream, run intelligence + synthesis workers,
verify items come out the other end as audio.
"""
import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")

GLM_API_KEY = os.getenv("GLM_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Realistic test items at different quality levels
TEST_ITEMS = [
    {
        "url": "https://example.com/gpt5-release",
        "title": "Claude 4 Opus 正式发布，推理能力突破新基准",
        "content": "Anthropic 今日发布 Claude 4 Opus 模型，在 MMLU、HumanEval 等主要基准上超越 GPT-5。"
                   "新模型支持 100 万 token 上下文，具备原生工具使用能力，"
                   "API 定价每百万 token 入站 15 美元、出站 75 美元。企业客户即日起可申请访问。",
        "source": "科技日报",
        "published_at": datetime.now().isoformat(),
        "channel_id": "2d253a46",
    },
    {
        "url": "https://example.com/zhipu-glm5",
        "title": "智谱 AI 发布 GLM-5，多模态能力全面升级",
        "content": "智谱 AI 今日在北京发布 GLM-5 系列大模型，包括 GLM-5-Flash、GLM-5-Pro 和 GLM-5-Vision 三款产品。"
                   "官方测试显示，GLM-5-Pro 在中文理解、数学推理、代码生成三项能力上达到同类产品领先水平。"
                   "GLM-5-Flash 推理成本较上一代降低 70%，面向企业用户开放 API。",
        "source": "36氪",
        "published_at": datetime.now().isoformat(),
        "channel_id": "2d253a46",
    },
    {
        "url": "https://example.com/boring-news",
        "title": "某 AI 初创公司完成 500 万美元天使轮融资",
        "content": "总部位于硅谷的 AI 初创公司 AIStar 今日宣布完成 500 万美元天使轮融资，"
                   "由知名风投机构领投。公司表示将利用本轮资金扩大团队规模，加速产品开发。",
        "source": "TechCrunch",
        "published_at": datetime.now().isoformat(),
        "channel_id": "2d253a46",
    },
]

RAW_STREAM = "signal:raw"
SCRIPT_STREAM = "signal:scripts"
AUDIO_STREAM = "signal:audio"


async def main():
    import redis.asyncio as aioredis
    from backend.intelligence.worker import IntelligenceWorker
    from backend.synthesis.worker import SynthesisWorker

    r = aioredis.from_url(REDIS_URL)

    # Clean up old test streams
    for stream in [RAW_STREAM, SCRIPT_STREAM, AUDIO_STREAM]:
        await r.delete(stream)

    print("\n" + "═" * 60)
    print("  SIGNAL FM · Redis Stream Worker 集成测试")
    print("═" * 60)

    # Push test items into raw stream
    print(f"\n📤 注入 {len(TEST_ITEMS)} 条原始条目到 Redis Stream...")
    for item in TEST_ITEMS:
        msg_id = await r.xadd(RAW_STREAM, item)
        print(f"  ✅ {msg_id.decode()} → {item['title'][:50]}")

    channels = {
        "2d253a46": {
            "id": "2d253a46",
            "topic": "AI 大模型与科技产品最新进展",
            "preference": "优先播报 GPT、Claude、Gemini、GLM 等大模型的突破进展，淡化纯融资新闻",
            "style": "formal",
        }
    }

    # Run intelligence worker
    print(f"\n🧠 运行 Intelligence Worker（GLM-4-Flash 评分 + GLM-4 生成）...")
    intel_worker = IntelligenceWorker(r, GLM_API_KEY, channels)
    await intel_worker.setup()

    # Process all pending messages
    messages = await r.xreadgroup(
        "intelligence", "worker-1",
        {RAW_STREAM: ">"},
        count=20,
        block=1000,
    )
    for _stream, entries in messages:
        for msg_id, fields in entries:
            await intel_worker._process(msg_id, fields)

    # Check script stream
    scripts = await r.xrange(SCRIPT_STREAM)
    print(f"\n📝 Script Stream 中有 {len(scripts)} 条播报稿（通过评分阈值）")
    for msg_id, fields in scripts:
        d = {k.decode(): v.decode() for k, v in fields.items()}
        score = int(d.get("score", 0))
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        print(f"  [{bar}] {score}/100 — {d['title'][:55]}")

    # Run synthesis worker
    print(f"\n🔊 运行 Synthesis Worker（Edge TTS）...")
    synth_worker = SynthesisWorker(r)
    await synth_worker.setup()

    messages = await r.xreadgroup(
        "synthesis", "tts-worker-1",
        {SCRIPT_STREAM: ">"},
        count=10,
        block=1000,
    )
    for _stream, entries in messages:
        for msg_id, fields in entries:
            await synth_worker._process(msg_id, fields)

    # Check audio stream
    audio_msgs = await r.xrange(AUDIO_STREAM)
    print(f"\n🎵 Audio Stream 中有 {len(audio_msgs)} 条音频就绪")
    for msg_id, fields in audio_msgs:
        d = {k.decode(): v.decode() for k, v in fields.items()}
        from pathlib import Path
        p = Path(d.get("audio_path", ""))
        size = f"{p.stat().st_size // 1024} KB" if p.exists() else "文件缺失"
        print(f"  🎵 [{d['score']}分] {d['title'][:50]}")
        print(f"      音频: {p.name[:40]}  ({size})")

    print(f"\n{'═' * 60}")
    print(f"  Worker 测试完成")
    print(f"  {len(TEST_ITEMS)} 条输入 → {len(scripts)} 条评分通过 → {len(audio_msgs)} 条音频")
    print("═" * 60 + "\n")

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
