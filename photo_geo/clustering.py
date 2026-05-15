from datetime import timedelta
from .models import Cluster, PhotoRecord

def cluster_by_time(records: list[PhotoRecord], max_gap_minutes: int = 20) -> list[Cluster]:
    items = [r for r in records if r.taken_at is not None]
    items.sort(key=lambda r: r.taken_at)
    clusters = []
    if not items:
        return clusters
    max_gap = timedelta(minutes=max_gap_minutes)
    current = Cluster(id=0, photos=[items[0]], start=items[0].taken_at, end=items[0].taken_at)
    items[0].cluster_id = 0
    for rec in items[1:]:
        prev = current.photos[-1]
        if rec.taken_at - prev.taken_at <= max_gap:
            current.photos.append(rec)
            current.end = rec.taken_at
            rec.cluster_id = current.id
        else:
            clusters.append(current)
            current = Cluster(id=len(clusters), photos=[rec], start=rec.taken_at, end=rec.taken_at)
            rec.cluster_id = current.id
    clusters.append(current)
    return clusters

def cluster_stats(clusters: list[Cluster]) -> dict:
    total = len(clusters)
    with_geo = sum(1 for c in clusters if any(p.has_gps for p in c.photos))
    return {
        'clusters': total,
        'clusters_with_geo': with_geo,
        'clusters_without_geo': total - with_geo,
        'photos_in_clusters': sum(len(c.photos) for c in clusters),
    }

def _cluster_center_time(c: Cluster):
    return c.start + (c.end - c.start) / 2 if c.start and c.end else c.start or c.end

def infer_cluster_locations(clusters: list[Cluster]) -> None:
    anchors = [c for c in clusters if any(p.has_gps and p.lat is not None and p.lon is not None for p in c.photos)]
    for c in clusters:
        aps = [p for p in c.photos if p.has_gps and p.lat is not None and p.lon is not None]
        if aps:
            c.inferred_lat = sum(p.lat for p in aps) / len(aps)
            c.inferred_lon = sum(p.lon for p in aps) / len(aps)
            c.confidence = min(1.0, 0.5 + 0.1 * len(aps))
            c.source = 'anchors'
            continue
        ct = _cluster_center_time(c)
        if ct is None or not anchors:
            c.source = 'unresolved'
            c.confidence = 0.0
            continue
        best = None
        best_dist = None
        for a in anchors:
            at = _cluster_center_time(a)
            if at is None:
                continue
            dist = abs((ct - at).total_seconds())
            if best_dist is None or dist < best_dist:
                best = a
                best_dist = dist
        if best is None:
            c.source = 'unresolved'
            c.confidence = 0.0
            continue
        baps = [p for p in best.photos if p.has_gps and p.lat is not None and p.lon is not None]
        if not baps:
            c.source = 'unresolved'
            c.confidence = 0.0
            continue
        c.inferred_lat = sum(p.lat for p in baps) / len(baps)
        c.inferred_lon = sum(p.lon for p in baps) / len(baps)
        c.source = f'nearest_anchor:{best.id}'
        hours = best_dist / 3600.0
        c.confidence = max(0.0, min(1.0, 1.0 - hours / 12.0))

def mixed_clusters(clusters: list[Cluster]) -> list[Cluster]:
    return [c for c in clusters if any(p.has_gps for p in c.photos) and any(not p.has_gps for p in c.photos)]
