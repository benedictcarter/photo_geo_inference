import argparse
from pathlib import Path

from .scanner import collect_photo_paths, scan_photos
from .clustering import cluster_by_time, cluster_stats, infer_cluster_locations, mixed_clusters
from .gui import ClusterReviewer


def main():
    version = "v61-clean-flags"
    print(f"photo_geo {version}")

    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("--minutes", type=int, default=20, help="time gap in minutes")
    args = p.parse_args()

    root = Path(args.root)
    print(f"[1/4] Counting photo files under: {root}")
    paths = collect_photo_paths(root)
    print(f"[2/4] Found {len(paths)} candidate photo files")
    print(f"[3/4] Scanning EXIF on {len(paths)} files")
    records = scan_photos(paths, debug=False)
    print(f"[3/4 done] Scan complete: {len(records)} photos | {sum(1 for r in records if r.has_gps)} with geo | {sum(1 for r in records if not r.has_gps)} without geo")

    clusters = cluster_by_time(records, args.minutes)
    infer_cluster_locations(clusters)
    stats = cluster_stats(clusters)

    print(f"[4/4] Clustering by time gap: {args.minutes} minutes")
    print(f"Clusters found: {stats['clusters']} | with geo: {stats['clusters_with_geo']} | without geo: {stats['clusters_without_geo']} | photos in clusters: {stats['photos_in_clusters']}")

    review = mixed_clusters(clusters)
    print(f"Review clusters: {len(review)}")
    ClusterReviewer(review).run()


if __name__ == "__main__":
    main()
