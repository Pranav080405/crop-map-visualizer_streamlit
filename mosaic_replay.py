"""Replay an existing GeoTIFF mosaic as a live stream (1 tile per second) for demos.
  pip install rasterio            (put this file next to orin_sender.py)
  python mosaic_replay.py mosaic.tif http://<server>:8000 secret [--tile 1024] [--delay 1]
RGB-only mosaic (default): the NDVI/NDRE tabs show STAND-INS, (G-R)/(G+R) and (G-B)/(G+B), not real indices.
Multispectral mosaic: give 1-based band numbers, e.g.  --rgb 1 2 3 --red 6 --re 7 --nir 5
"""
import argparse, time
import numpy as np, rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import Window, bounds as win_bounds
from orin_sender import Sender

ap = argparse.ArgumentParser()
ap.add_argument("tif"); ap.add_argument("url"); ap.add_argument("key")
ap.add_argument("--tile", type=int, default=1024, help="tile size in pixels")
ap.add_argument("--delay", type=float, default=1.0, help="seconds between tiles")
ap.add_argument("--rgb", type=int, nargs=3, default=[1, 2, 3])
ap.add_argument("--red", type=int); ap.add_argument("--re", type=int); ap.add_argument("--nir", type=int)
a = ap.parse_args()


def to8(x):
    if x.dtype == np.uint8:
        return x
    return (np.clip(x / (65535.0 if x.dtype == np.uint16 else 1.0), 0, 1) * 255).astype(np.uint8)


s, sent = Sender(a.url, a.key), 0
with rasterio.open(a.tif) as src:
    if src.crs is None:
        raise SystemExit("Mosaic has no CRS: use a georeferenced GeoTIFF.")
    T, cols = a.tile, list(range(0, src.width, a.tile))
    for ri, row in enumerate(range(0, src.height, T)):
        for col in (cols if ri % 2 == 0 else cols[::-1]):  # snake across rows like a survey flight
            win = Window(col, row, min(T, src.width - col), min(T, src.height - row))
            d = src.read(window=win)
            valid = ((src.read_masks(1, window=win) > 0) & d.any(0)).astype(np.uint8)
            if valid.mean() < .05:
                continue  # skip empty border tiles
            w, so, e, n = transform_bounds(src.crs, "EPSG:4326", *win_bounds(win, src.transform))
            R, G, B = (to8(d[i - 1]) for i in a.rgb)
            rgb = np.dstack([B, G, R])  # BGR for OpenCV
            if a.nir and a.red and a.re:
                nir, r, re = (d[i - 1].astype(np.float32) for i in (a.nir, a.red, a.re))
            else:  # stand-in indices, encoded as band values whose normalized difference equals them
                R, G, B = (x.astype(np.float32) + 1 for x in (R, G, B))
                s1 = np.clip(((G - R) / (G + R) + .05) / .35, 0, 1)    # shown on the 0..1 NDVI scale
                s2 = np.clip((G - B) / (G + B) / .3, 0, 1) * .6        # shown on the 0..0.6 NDRE scale
                nir, r, re = np.ones_like(G), (1 - s1) / (1 + s1), (1 - s2) / (1 + s2)
            s.send(rgb, r, re, nir, [[so, w], [n, e]], valid=valid)
            sent += 1
            time.sleep(a.delay)
s.q.join()
print("sent", sent, "tiles")