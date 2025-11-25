from pydantic import BaseModel
from typing import Optional

class VideoCard(BaseModel):
    video_id: str
    title: str
    channel_title: str
    thumbnail_url: str
    published_at: str
    channel_id: str

class SwipeAction(BaseModel):
    video_id: str
    action: str  # "save" or "skip"
    playlist_id: Optional[str] = None
