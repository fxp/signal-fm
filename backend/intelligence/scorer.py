"""
AI scoring engine: GLM-4-Flash四维评分，阈值≥70才入队。
Dimensions: novelty(30) + importance(30) + relevance(20) + urgency(20)
"""
import json
import logging
from dataclasses import dataclass

from zhipuai import ZhipuAI

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 70

SCORE_PROMPT = """\
你是 Signal FM 的内容评分引擎。请对以下新闻内容进行四维评分，输出纯 JSON，不要任何解释。

频道主题：{channel_topic}
频道偏好（用户自定义）：{channel_preference}

新闻标题：{title}
新闻来源：{source}
新闻摘要：{content}

评分标准（每维满分为括号内数字）：
- novelty（30分）：信息是否为首次报道或独家，是否带来新增量
- importance（30分）：对该领域的影响程度和深度
- relevance（20分）：与频道主题的匹配程度
- urgency（20分）：内容时效性，是否需要立即知晓

请严格按如下格式输出：
{{
  "novelty": <0-30>,
  "importance": <0-30>,
  "relevance": <0-20>,
  "urgency": <0-20>,
  "total": <合计>,
  "reason": "<一句话说明评分理由>"
}}
"""


@dataclass
class ScoreResult:
    novelty: int
    importance: int
    relevance: int
    urgency: int
    total: int
    reason: str

    @property
    def qualifies(self) -> bool:
        return self.total >= SCORE_THRESHOLD


class Scorer:
    def __init__(self, api_key: str, model: str = "glm-4-flash"):
        self.client = ZhipuAI(api_key=api_key)
        self.model = model

    async def score(
        self,
        title: str,
        content: str,
        source: str,
        channel_topic: str,
        channel_preference: str = "",
    ) -> ScoreResult:
        prompt = SCORE_PROMPT.format(
            channel_topic=channel_topic,
            channel_preference=channel_preference or "无特殊偏好",
            title=title,
            source=source,
            content=content[:800],
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=256,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            return ScoreResult(
                novelty=int(data.get("novelty", 0)),
                importance=int(data.get("importance", 0)),
                relevance=int(data.get("relevance", 0)),
                urgency=int(data.get("urgency", 0)),
                total=int(data.get("total", 0)),
                reason=data.get("reason", ""),
            )
        except Exception as e:
            logger.warning(f"Score failed for '{title[:40]}': {e}")
            return ScoreResult(0, 0, 0, 0, 0, f"error: {e}")
