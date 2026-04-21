"""
Feedback calibrator: analyzes thumbs up/down data and refines channel
preference text using GLM-4. Runs every hour via APScheduler.
"""
import json
import logging

import redis.asyncio as redis
from zhipuai import ZhipuAI

logger = logging.getLogger(__name__)

FEEDBACK_THRESHOLD = 5  # min feedbacks before calibrating


CALIBRATE_PROMPT = """\
你是 Signal FM 的内容策略助手。用户对以下频道的播报内容给出了反馈：

频道名称：{channel_name}
频道主题：{channel_topic}
当前播报偏好设置：{current_preference}

用户喜欢的内容（👍）：
{liked_items}

用户不喜欢的内容（👎）：
{disliked_items}

请根据用户反馈，在50字以内重新描述该频道的播报偏好，要求：
1. 保留用户明确喜欢的内容类型
2. 降低用户不喜欢的内容类型的优先级
3. 保持简洁，像自然语言描述一样
4. 直接输出偏好文字，不要任何解释或前缀

新的播报偏好："""


class FeedbackCalibrator:
    def __init__(self, redis_client: redis.Redis, api_key: str, channels: dict):
        self.redis = redis_client
        self.client = ZhipuAI(api_key=api_key)
        self.channels = channels  # shared reference to _channels dict in main.py

    async def calibrate_channel(self, channel_id: str) -> str | None:
        """Return updated preference string, or None if not enough data."""
        feedback_key = f"signal:feedback:{channel_id}"
        raw = await self.redis.lrange(feedback_key, 0, 99)
        if len(raw) < FEEDBACK_THRESHOLD:
            return None

        entries = [json.loads(r) for r in raw]
        liked = [e for e in entries if e.get("user_rating") == 1]
        disliked = [e for e in entries if e.get("user_rating") == -1]

        if not liked and not disliked:
            return None

        channel = self.channels.get(channel_id, {})

        liked_text = "\n".join(f"- {e['title']} (AI评分:{e['ai_score']})" for e in liked[:10]) or "（无）"
        disliked_text = "\n".join(f"- {e['title']} (AI评分:{e['ai_score']})" for e in disliked[:10]) or "（无）"

        prompt = CALIBRATE_PROMPT.format(
            channel_name=channel.get("name", "未命名频道"),
            channel_topic=channel.get("topic", ""),
            current_preference=channel.get("preference") or "（未设置）",
            liked_items=liked_text,
            disliked_items=disliked_text,
        )

        try:
            response = self.client.chat.completions.create(
                model="glm-4-flash",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100,
            )
            new_pref = response.choices[0].message.content.strip()
            logger.info(f"[calibrate] channel={channel_id} new_pref='{new_pref[:60]}'")
            return new_pref
        except Exception as e:
            logger.warning(f"[calibrate] GLM call failed: {e}")
            return None

    async def run_once(self):
        """Calibrate all channels that have enough feedback."""
        for channel_id, channel in list(self.channels.items()):
            new_pref = await self.calibrate_channel(channel_id)
            if new_pref and new_pref != channel.get("preference"):
                channel["preference"] = new_pref
                # Persist updated channel to Redis
                channels_key = "signal:channels"
                await self.redis.hset(channels_key, channel_id, json.dumps(channel))
                logger.info(
                    f"[calibrate] updated preference for '{channel.get('name')}': {new_pref[:50]}"
                )
