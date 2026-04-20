"""
Script generator: converts raw news into broadcast-ready oral scripts via GLM-4.
Hallucination prevention: forces source attribution, forbids invented data.
"""
import logging
from dataclasses import dataclass

from zhipuai import ZhipuAI

logger = logging.getLogger(__name__)

SCRIPT_PROMPT = """\
你是 Signal FM 的 AI 主播编辑。请将以下新闻改写为适合广播播报的口语化稿件。

要求：
1. 开头必须注明来源，格式为"据[来源]报道，..."
2. 语言口语化、自然流畅，适合 TTS 朗读
3. 长度控制在 100-200 字之间
4. 禁止添加原文中没有的数据、引用或事实
5. 播报风格：{style}
6. 结尾简洁，不需要总结语

新闻来源：{source}
新闻标题：{title}
新闻内容：{content}

直接输出播报稿，不要任何解释或标注：
"""

STYLES = {
    "formal": "严肃简报风格，简洁权威",
    "casual": "轻松点评风格，亲切自然",
    "deep": "深度解读风格，有分析有观点",
}


@dataclass
class BroadcastScript:
    text: str
    title: str
    source: str
    channel_id: str
    score: int
    url: str


class ScriptGenerator:
    def __init__(self, api_key: str, model: str = "glm-4"):
        self.client = ZhipuAI(api_key=api_key)
        self.model = model

    async def generate(
        self,
        title: str,
        content: str,
        source: str,
        channel_id: str,
        score: int,
        url: str,
        style: str = "formal",
    ) -> BroadcastScript | None:
        style_desc = STYLES.get(style, STYLES["formal"])
        prompt = SCRIPT_PROMPT.format(
            style=style_desc,
            source=source,
            title=title,
            content=content[:1500],
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=512,
            )
            text = response.choices[0].message.content.strip()
            return BroadcastScript(
                text=text,
                title=title,
                source=source,
                channel_id=channel_id,
                score=score,
                url=url,
            )
        except Exception as e:
            logger.warning(f"Script gen failed for '{title[:40]}': {e}")
            return None
