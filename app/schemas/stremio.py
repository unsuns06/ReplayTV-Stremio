from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class Manifest(BaseModel):
    id: str
    version: str
    name: str
    description: str
    logo: Optional[str] = None
    background: Optional[str] = None
    resources: List[str]
    types: List[str]
    catalogs: List[Dict[str, Any]]
    idPrefixes: Optional[List[str]] = None
    behaviorHints: Optional[Dict[str, Any]] = None

class MetaPreview(BaseModel):
    id: str
    type: str
    name: str
    poster: Optional[str] = None
    logo: Optional[str] = None
    description: Optional[str] = None
    genres: Optional[List[str]] = None
    background: Optional[str] = None
    # Enhanced metadata fields for FranceTV
    fanart: Optional[str] = None
    banner: Optional[str] = None
    clearart: Optional[str] = None
    clearlogo: Optional[str] = None
    landscape: Optional[str] = None
    # Additional metadata
    year: Optional[int] = None
    rating: Optional[str] = None
    runtime: Optional[int] = None

class MetaDetail(BaseModel):
    id: str
    type: str
    name: str
    poster: Optional[str] = None
    logo: Optional[str] = None
    description: Optional[str] = None
    genres: Optional[List[str]] = None
    background: Optional[str] = None
    videos: Optional[List[Dict[str, Any]]] = None
    # Enhanced metadata fields for FranceTV
    fanart: Optional[str] = None
    banner: Optional[str] = None
    clearart: Optional[str] = None
    clearlogo: Optional[str] = None
    landscape: Optional[str] = None
    # Additional metadata
    year: Optional[int] = None
    rating: Optional[str] = None
    runtime: Optional[int] = None
    # Series specific fields
    season: Optional[int] = None
    episode: Optional[int] = None
    director: Optional[str] = None
    cast: Optional[List[str]] = None
    castandrole: Optional[List[List[str]]] = None
    # FranceTV specific fields
    channel: Optional[str] = None
    broadcast_date: Optional[str] = None
    duration: Optional[str] = None

class Video(BaseModel):
    id: str
    title: str
    season: Optional[int] = None
    episode: Optional[int] = None
    thumbnail: Optional[str] = None
    # Enhanced video metadata
    description: Optional[str] = None
    released: Optional[str] = None  # ISO 8601 date for Stremio
    duration: Optional[str] = None
    broadcast_date: Optional[str] = None
    rating: Optional[str] = None
    director: Optional[str] = None
    cast: Optional[List[str]] = None
    # FranceTV specific fields
    channel: Optional[str] = None
    program: Optional[str] = None
    type: Optional[str] = None  # 'integrale', 'extrait', etc.

class Stream(BaseModel):
    url: str
    title: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    externalUrl: Optional[str] = None
    manifest_type: Optional[str] = None
    licenseUrl: Optional[str] = None
    licenseHeaders: Optional[Dict[str, str]] = None

class CatalogResponse(BaseModel):
    metas: List[MetaPreview]

class MetaResponse(BaseModel):
    meta: MetaDetail

class StreamResponse(BaseModel):
    streams: List[Stream]