from pydantic import BaseModel
from typing import Optional


class ChannelCreate(BaseModel):
    name: str
    topic: str
    rss_feeds: list[str] = []
    keywords: list[str] = []
    preference: str = ""
    style: str = "formal"
    interval_minutes: int = 15


class ChannelResponse(BaseModel):
    id: str
    name: str
    topic: str
    rss_feeds: list[str]
    keywords: list[str]
    preference: str
    style: str
    interval_minutes: int


class NowPlayingResponse(BaseModel):
    status: str
    title: Optional[str] = None
    source: Optional[str] = None
    score: Optional[int] = None
    score_reason: Optional[str] = None
    url: Optional[str] = None
    channel_id: Optional[str] = None


class QueueItem(BaseModel):
    title: str
    source: str
    score: int
    channel_id: str
