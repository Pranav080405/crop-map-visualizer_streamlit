"""Orin side. pip install requests numpy opencv-python   (cv2 already ships with JetPack)
Call Sender.send(...) once per 1-s frame set. Test without a drone/camera:
  python orin_sender.py http://<server>:8000 secret
"""
import json, queue, sys, threading, time
import cv2, numpy as np, requests

X = np.linspace(0, 1, 256)
# greyscale lookup table: black (low index) -> white (high index)
LUT = np.repeat((X * 255).astype(np.uint8)[:, None, None], 3, axis=2)


def nd(a, b):
    return (a - b) / np.maximum(a + b, 1e-6)


def colorize(idx, lo, hi, valid):
    u8 = (np.clip((idx - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    return np.dstack([cv2.applyColorMap(u8, LUT), valid * 255])


def webp(img, q=80, max_px=1280):  # lower q / max_px to cut bandwidth
    s = max_px / max(img.shape[:2])
    if s < 1:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return cv2.imencode(".webp", img, [cv2.IMWRITE_WEBP_QUALITY, q])[1].tobytes()


class Sender:
    def __init__(self, url, key):
        self.url = url.rstrip("/") + "/api/tile"
        self.http = requests.Session(); self.http.headers["X-Api-Key"] = key
        self.q = queue.Queue(maxsize=3)  # on a slow link the oldest queued tile is dropped
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            meta, files = self.q.get()
            try:
                self.http.post(self.url, data={"meta": meta}, files=files, timeout=8).raise_for_status()
            except Exception as e:
                print("send failed:", e)
            self.q.task_done()

    def send(self, rgb, r, re, nir, bounds, valid=None):
        """rgb HxWx3 uint8 BGR; r, re, nir HxW reflectance on the same north-up grid;
        bounds [[south, west], [north, east]] in lat/lon; valid HxW uint8 (1 = data)."""
        r, re, nir = (np.asarray(x, np.float32) for x in (r, re, nir))
        if valid is None:
            valid = (nir + r > 0).astype(np.uint8)
        if rgb.shape[:2] != valid.shape:
            rgb = cv2.resize(rgb, valid.shape[::-1])
        files = {"rgb": ("rgb.webp", webp(np.dstack([rgb, valid * 255]))),
                 "ndvi": ("ndvi.webp", webp(colorize(nd(nir, r), 0, 1, valid))),
                 "ndre": ("ndre.webp", webp(colorize(nd(nir, re), 0, 0.6, valid)))}
        if self.q.full():
            try:
                self.q.get_nowait(); self.q.task_done()
            except queue.Empty:
                pass
        self.q.put((json.dumps({"bounds": bounds, "t": time.time()}), files))


if __name__ == "__main__":  # synthetic lawnmower flight
    s = Sender(sys.argv[1], sys.argv[2]); d, H = 2e-4, 256
    for i in range(60):
        row, col = divmod(i, 10); col = col if row % 2 == 0 else 9 - col
        s0, w0 = 36.0 + row * d * .8, -119.0 + col * d * .8
        la = np.linspace(s0 + d, s0, H)[:, None]; lo = np.linspace(w0, w0 + d, H)[None, :]
        veg = (np.sin(la * 6e4) * np.sin(lo * 6e4) > -.2).astype(np.float32)
        nir, r, re, g = .15 + .45 * veg, .25 - .2 * veg, .2 + .2 * veg, .12 + .06 * veg
        rgb = np.clip(np.dstack([g, g * 2, r]) * 255, 0, 255).astype(np.uint8)
        s.send(rgb, r, re, nir, [[s0, w0], [s0 + d, w0 + d]])
        time.sleep(1)
    s.q.join()