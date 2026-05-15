from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import Optional

@dataclass
class PhotoRecord:
    path: Path
    folder: Path
    taken_at: Optional[datetime] = None
    has_gps: bool = False
    lat: Optional[float] = None
    lon: Optional[float] = None
    cluster_id: Optional[int] = None

@dataclass
class Cluster:
    id: int
    photos: list[PhotoRecord] = field(default_factory=list)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    inferred_lat: Optional[float] = None
    inferred_lon: Optional[float] = None
    confidence: float = 0.0
    source: str = "unknown"
