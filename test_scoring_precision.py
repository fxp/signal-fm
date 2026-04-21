"""
Scoring precision test: inject mixed content (AI/tech vs. unrelated),
verify the scoring engine correctly separates signal from noise.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.WARNING)

GLM_API_KEY = os.getenv("GLM_API_KEY", "")

CHANNEL = {
    "topic": "AI 大模型、芯片、算法突破，以及对全球科技格局的影响",
    "preference": (
        "重点：GPT/Claude/Gemini/GLM 等大模型发布或能力突破；英伟达/AMD 芯片进展；"
        "AI 安全监管政策；AI 对就业/社会的重大影响。"
        "淡化：普通企业融资（<5亿）；娱乐明星；体育赛事；房地产；消费品促销。"
    ),
}

# Mix of high-signal and noise items
TEST_ITEMS = [
    # HIGH signal
    {"title": "OpenAI 发布 o3 模型，数学竞赛成绩首次超越人类专家",
     "content": "OpenAI 发布最新推理模型 o3，在 AIME 数学竞赛中得分 96.7 分，超越人类金牌选手平均成绩。在 SWE-bench 软件工程基准上达到 71.7%，较前代提升 20 个百分点。OpenAI CEO Sam Altman 称这标志 AI 推理能力进入新阶段。",
     "source": "MIT Tech Review", "expected": "high"},

    {"title": "英伟达 Blackwell Ultra GPU 量产，AI 算力提升 4 倍",
     "content": "英伟达宣布 Blackwell Ultra 架构 GPU 开始量产交付，单卡 FP8 算力达 20 PFLOPS，较 H100 提升近 4 倍。主要客户包括微软 Azure、谷歌 GCP、亚马逊 AWS。英伟达 CEO 黄仁勋表示需求远超供给。",
     "source": "彭博社", "expected": "high"},

    {"title": "欧盟 AI 法案正式生效，GPT-5 等通用 AI 面临新合规要求",
     "content": "欧盟《人工智能法案》今日正式生效，将对高风险 AI 系统实施严格监管。OpenAI、Google、Anthropic 等公司必须在 12 个月内完成合规审计，否则面临最高全球营收 3% 的罚款。",
     "source": "路透社", "expected": "high"},

    # MID signal
    {"title": "字节跳动推出 AI 视频生成工具，对标 Sora",
     "content": "字节跳动旗下剪映推出 AI 视频生成功能，用户输入文字即可生成 30 秒视频。该功能基于公司内部大模型，目前向 Pro 版用户开放。定价每月 99 元。",
     "source": "36氪", "expected": "mid"},

    {"title": "某 AI 初创公司完成 3000 万美元 A 轮融资",
     "content": "专注于 AI 客服的初创公司 ChatBot Pro 宣布完成 3000 万美元 A 轮融资，投资方为某中型风投机构。公司称将用于扩招和产品迭代。目前客户数量约 50 家。",
     "source": "TechCrunch", "expected": "low"},

    # LOW signal / noise
    {"title": "五一假期国内旅游人数预计超 3 亿，酒店提前爆满",
     "content": "文旅部预计今年五一黄金周国内旅游出行人次将超过 3 亿，同比增长 15%。三亚、丽江、西藏等热门目的地酒店早已爆满。建议游客提前做好出行规划。",
     "source": "央视新闻", "expected": "low"},

    {"title": "小鬼王琳凯新专辑首日销量破百万，粉丝应援创纪录",
     "content": "歌手王琳凯今日发行第三张个人专辑《盛夏》，首日数字销量突破百万张，创其个人记录。粉丝在各大社交平台发起应援活动，相关话题阅读量超 5 亿。",
     "source": "娱乐周刊", "expected": "low"},

    {"title": "2026 年 NBA 季后赛：湖人队出局，勇士晋级四强",
     "content": "昨日 NBA 季后赛激战，洛杉矶湖人队以 3 比 4 负于丹佛掘金队无缘八强，金州勇士队以 4 比 2 晋级四强将与波士顿凯尔特人对决。",
     "source": "ESPN", "expected": "low"},

    {"title": "房地产市场回暖信号：北京二手房成交量连续三月上涨",
     "content": "链家数据显示，北京二手房成交量已连续三个月环比上涨，4 月均价微涨 1.2%。业内人士认为，政策托底效果正在显现，但整体市场仍处于温和修复阶段。",
     "source": "财经日报", "expected": "low"},
]


async def main():
    from backend.intelligence.scorer import Scorer, SCORE_THRESHOLD

    scorer = Scorer(GLM_API_KEY)
    print("\n" + "═" * 65)
    print("  SIGNAL FM · 评分精准度测试")
    print(f"  频道: {CHANNEL['topic'][:50]}")
    print(f"  入队阈值: ≥{SCORE_THRESHOLD}")
    print("═" * 65)

    results = {"high": [], "mid": [], "low": []}
    all_scores = []

    for item in TEST_ITEMS:
        result = await scorer.score(
            title=item["title"],
            content=item["content"],
            source=item["source"],
            channel_topic=CHANNEL["topic"],
            channel_preference=CHANNEL["preference"],
        )
        bar = "█" * (result.total // 10) + "░" * (10 - result.total // 10)
        qualifier = "✅ 入队" if result.qualifies else "❌ 过滤"
        expected = item["expected"]
        correct = (
            (expected == "high" and result.qualifies) or
            (expected == "low" and not result.qualifies) or
            (expected == "mid")  # mid can go either way
        )
        mark = "✓" if correct else "✗"

        print(f"\n  {mark} [{bar}] {result.total:3d} {qualifier}")
        print(f"    {item['title'][:58]}")
        print(f"    来源:{item['source']} 预期:{expected} → 实际:{'通过' if result.qualifies else '过滤'}")

        results[expected].append(result.total)
        all_scores.append((item["title"], result.total, result.qualifies, expected))

    # Summary
    print(f"\n{'═' * 65}")
    passed = [s for _, s, q, _ in all_scores if q]
    filtered = [s for _, s, q, _ in all_scores if not q]
    high_passed = sum(1 for _, s, q, e in all_scores if q and e == "high")
    low_filtered = sum(1 for _, s, q, e in all_scores if not q and e == "low")
    high_total = sum(1 for _, _, _, e in all_scores if e == "high")
    low_total = sum(1 for _, _, _, e in all_scores if e == "low")

    print(f"  通过评分: {len(passed)}/{len(TEST_ITEMS)} 条")
    print(f"  过滤掉:  {len(filtered)}/{len(TEST_ITEMS)} 条")
    print(f"  高信号命中率: {high_passed}/{high_total} ({'%.0f' % (high_passed/high_total*100)}%)")
    print(f"  噪声过滤率:   {low_filtered}/{low_total} ({'%.0f' % (low_filtered/low_total*100)}%)")
    if results["high"]:
        print(f"  高信号平均分: {sum(results['high'])/len(results['high']):.1f}")
    if results["low"]:
        print(f"  噪声平均分:   {sum(results['low'])/len(results['low']):.1f}")
    print("═" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
