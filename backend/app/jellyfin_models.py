from pydantic import BaseModel
from typing import Optional


class AuthByNameRequest(BaseModel):
    Username: str = ""
    username: str = ""
    Pw: str = ""
    password: str = ""


class PlayingRequest(BaseModel):
    ItemId: str = ""
    SessionId: str = ""
    PlaySessionId: str = ""
    PositionTicks: int = 0
    IsPaused: bool = False
    IsMuted: bool = False
    AudioStreamIndex: Optional[int] = None
    SubtitleStreamIndex: Optional[int] = None
    MediaSourceId: str = ""
    CanSeek: bool = True


class PlaybackInfoRequest(BaseModel):
    UserId: str = ""
    StartTimeTicks: int = 0
    AudioStreamIndex: Optional[int] = None
    SubtitleStreamIndex: Optional[int] = None
    MaxStreamingBitrate: Optional[int] = None
    EnableDirectPlay: bool = True
    EnableDirectStream: bool = True
    EnableTranscoding: bool = False
    AllowVideoStreamCopy: bool = True
    AllowAudioStreamCopy: bool = True
    DeviceProfile: Optional[dict] = None
