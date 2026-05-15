import piexif

def make_gps_exif(lat, lon):
    def dec_to_dms(x):
        x = abs(float(x))
        d = int(x)
        m_float = (x - d) * 60
        m = int(m_float)
        s = int(round((m_float - m) * 60 * 10000))
        return (d, 1), (m, 1), (s, 10000)

    lat_ref = "N" if lat >= 0 else "S"
    lon_ref = "E" if lon >= 0 else "W"

    return {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref.encode("ascii"),
        piexif.GPSIFD.GPSLatitude: dec_to_dms(lat),
        piexif.GPSIFD.GPSLongitudeRef: lon_ref.encode("ascii"),
        piexif.GPSIFD.GPSLongitude: dec_to_dms(lon),
    }


def write_cluster_gps(cluster):
    """
    Write inferred GPS for all non-GPS photos in this cluster.
    Returns number of photos written.
    """
    if cluster.inferred_lat is None or cluster.inferred_lon is None:
        return 0

    gps_ifd = make_gps_exif(cluster.inferred_lat, cluster.inferred_lon)
    written = 0

    for p in cluster.photos:
        if p.has_gps:
            continue

        try:
            exif_dict = piexif.load(str(p.path))
            exif_dict.setdefault("GPS", {})
            exif_dict["GPS"].update(gps_ifd)
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, str(p.path))
        except Exception:
            continue

        p.has_gps = True
        p.lat = cluster.inferred_lat
        p.lon = cluster.inferred_lon
        written += 1

    return written