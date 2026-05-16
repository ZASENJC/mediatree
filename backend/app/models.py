from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Movie(BaseModel):
    id: Optional[int] = None
    path: str
    code: str
    title: Optional[str] = None
    actress: Optional[str] = None
    release_date: Optional[str] = None
    duration: Optional[int] = None
    cover_local: Optional[str] = None
    cover_remote: Optional[str] = None
    fanart_local: Optional[str] = None
    javdb_url: Optional[str] = None
    javdb_score: Optional[float] = None
    javdb_likes: Optional[int] = None
    javdb_thumbnails: Optional[str] = None
    folder_levels: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JavdbCache(BaseModel):
    id: Optional[int] = None
    code: str
    data: str
    fetched_at: Optional[str] = None


class Category(BaseModel):
    id: Optional[int] = None
    name: str
    movie_ids: Optional[str] = None
    created_at: Optional[str] = None


class Tag(BaseModel):
    id: Optional[int] = None
    movie_id: int
    tag: str


class ScanResult(BaseModel):
    total: int
    new_codes: list[str]
    removed: list[str]
    errors: list[str]


class ConfigUpdate(BaseModel):
    javdb_cookie: Optional[str] = None
    javdb_enabled: Optional[bool] = None
    javdb_cache_hours: Optional[int] = None


class FolderNode(BaseModel):
    name: str
    path: str
    is_leaf: bool = False
    movie_count: int = 0
    cover: Optional[str] = None
    children: Optional[list["FolderNode"]] = None
