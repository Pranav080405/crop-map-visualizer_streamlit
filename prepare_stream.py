# prepare_stream.py
import json
import base64
from pathlib import Path
import cv2
import numpy as np

INPUT_IMAGE = "pistachio_2d_mosaic.png"
TILE_SIZE = 512  # px per tile chunk
OUTPUT_JSON = Path("static/tiles.json")
OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

X = np.linspace(0, 1, 256)
LUT = np.repeat((X * 255).astype(np.uint8)[:, None, None], 3, axis=2)

def to_base64_webp(img_bgra, q=80):
    buf = cv2.imencode(".webp", img_bgra, [cv2.IMWRITE_WEBP_QUALITY, q])[1].tobytes()
    return f"data:image/webp;base64,{base64.b64encode(buf).decode('utf-8')}"

def colorize(idx, lo, hi, valid):
    u8 = (np.clip((idx - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    return np.dstack([cv2.applyColorMap(u8, LUT), valid * 255])

def main():
    print(f"Loading {INPUT_IMAGE}...")
    img = cv2.imread(INPUT_IMAGE, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not find {INPUT_IMAGE}")

    H, W = img.shape[:2]
    tiles = []

    cols = list(range(0, W, TILE_SIZE))
    rows = list(range(0, H, TILE_SIZE))

    for ri, y in enumerate(rows):
        cur_cols = cols if ri % 2 == 0 else cols[::-1]
        for x in cur_cols:
            w_box = min(TILE_SIZE, W - x)
            h_box = min(TILE_SIZE, H - y)

            crop = img[y:y + h_box, x:x + w_box]
            valid = (crop.sum(axis=2) > 0).astype(np.uint8)

            # Skip empty border / black background regions
            if valid.mean() < 0.05:
                continue

            # 1. RGB
            rgb_tile = np.dstack([crop, valid * 255])

            # 2. Stand-in synthetic indices
            B = crop[:, :, 0].astype(np.float32) + 1.0
            G = crop[:, :, 1].astype(np.float32) + 1.0
            R = crop[:, :, 2].astype(np.float32) + 1.0

            s1 = np.clip(((G - R) / (G + R) + 0.05) / 0.35, 0.0, 1.0)
            ndvi_tile = colorize(s1, 0.0, 1.0, valid)

            s2 = np.clip((G - B) / (G + B) / 0.3, 0.0, 1.0) * 0.6
            ndre_tile = colorize(s2, 0.0, 0.6, valid)

            # Direct [y, x] to [y + h, x + w] pixel coordinate mapping
            bounds = [[int(y), int(x)], [int(y + h_box), int(x + w_box)]]

            tiles.append({
                "bounds": bounds,
                "rgb": to_base64_webp(rgb_tile),
                "ndvi": to_base64_webp(ndvi_tile),
                "ndre": to_base64_webp(ndre_tile)
            })

    manifest = {
        "dimensions": [H, W],
        "total_tiles": len(tiles),
        "tiles": tiles
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(manifest, f)

    print(f"Generated {len(tiles)} tiles -> {OUTPUT_JSON}")

if __name__ == "__main__":
    main()