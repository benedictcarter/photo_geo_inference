from pathlib import Path
from datetime import datetime
import exifread
from .models import PhotoRecord

IMAGE_EXTS = {".jpg", ".jpeg", ".tif", ".tiff"}

def collect_photo_paths(root: str | Path) -> list[Path]:
    root = Path(root)
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]

def _parse_taken_at(tags: dict):
    for key in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime", "DateTime"):
        value = tags.get(key)
        if value:
            try:
                return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
            except Exception:
                pass
    return None

def _to_decimal(coord, ref):
    vals = []
    for c in coord.values:
        try:
            vals.append(float(c.num) / float(c.den))
        except Exception:
            vals.append(float(c))
    while len(vals) < 3:
        vals.append(0.0)
    dec = vals[0] + vals[1] / 60.0 + vals[2] / 3600.0
    if str(ref.values[0]).upper().startswith(('S', 'W')):
        dec = -dec
    return dec

def _gps_from_tags(tags: dict):
    lat = tags.get('GPS GPSLatitude')
    lat_ref = tags.get('GPS GPSLatitudeRef')
    lon = tags.get('GPS GPSLongitude')
    lon_ref = tags.get('GPS GPSLongitudeRef')
    if not (lat and lat_ref and lon and lon_ref):
        return None, None
    try:
        return _to_decimal(lat, lat_ref), _to_decimal(lon, lon_ref)
    except Exception:
        return None, None

def scan_photos(paths: list[Path], debug: bool = True) -> list[PhotoRecord]:
    records = []
    total = len(paths)
    with_geo = 0
    for i, path in enumerate(paths, 1):
        try:
            with open(path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
        except Exception:
            tags = {}
        taken_at = _parse_taken_at(tags)
        lat, lon = _gps_from_tags(tags)
        has_gps = lat is not None and lon is not None
        has_gps = has_gps*(lat != 0 and lon != 0)
        if has_gps:
            with_geo += 1
        records.append(PhotoRecord(path=path, folder=path.parent, taken_at=taken_at, has_gps=has_gps, lat=lat, lon=lon))
        if debug and (i <= 5 or i % 1000 == 0 or i == total):
            sample = f"lat={lat:.6f}, lon={lon:.6f}" if has_gps else "no gps"
            print(f"  scanned {i}/{total} ({(i/total*100 if total else 100):5.1f}%) | geo {with_geo} | no-geo {len(records)-with_geo} | {sample}")
    return records
