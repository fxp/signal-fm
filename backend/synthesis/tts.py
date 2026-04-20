"""
TTS synthesis layer: Edge TTS (MVP) with local file caching via MinIO/filesystem.
CosyVoice can be plugged in as the primary engine in Phase 2.
"""
import asyncio
import hashlib
import logging
import os
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)

AUDIO_CACHE_DIR = Path(os.getenv("AUDIO_CACHE_DIR", "/tmp/signal-fm/audio"))
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Voice options for Edge TTS (Chinese voices)
VOICES = {
    "zh-CN-female": "zh-CN-XiaoxiaoNeural",
    "zh-CN-male": "zh-CN-YunxiNeural",
    "zh-TW-female": "zh-TW-HsiaoChenNeural",
}
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


class TTSSynthesizer:
    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice

    def _cache_path(self, text: str) -> Path:
        key = hashlib.sha256(f"{self.voice}:{text}".encode()).hexdigest()
        return AUDIO_CACHE_DIR / f"{key}.mp3"

    async def synthesize(self, text: str) -> Path:
        """Synthesize text to MP3, return path. Cached by content hash."""
        cache_path = self._cache_path(text)
        if cache_path.exists():
            logger.debug(f"[tts] cache hit: {cache_path.name}")
            return cache_path

        logger.info(f"[tts] synthesizing {len(text)} chars via Edge TTS")
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(str(cache_path))
        logger.info(f"[tts] saved: {cache_path.name}")
        return cache_path

    async def synthesize_ssml(self, ssml: str) -> Path:
        """Synthesize SSML markup."""
        cache_path = self._cache_path(ssml)
        if cache_path.exists():
            return cache_path

        communicate = edge_tts.Communicate(ssml, self.voice)
        communicate._texts = [(ssml, {})]  # pass SSML directly
        await communicate.save(str(cache_path))
        return cache_path


class TTSRouter:
    """Route TTS requests to primary (Edge TTS) or fallback engines."""

    def __init__(self, voice: str = DEFAULT_VOICE):
        self.primary = TTSSynthesizer(voice)

    async def synthesize(self, text: str) -> Path | None:
        try:
            return await self.primary.synthesize(text)
        except Exception as e:
            logger.error(f"[tts] primary failed: {e}")
            return None

    def set_voice(self, voice_key: str):
        voice = VOICES.get(voice_key, DEFAULT_VOICE)
        self.primary = TTSSynthesizer(voice)
