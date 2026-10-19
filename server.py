"""Live map server (FastAPI). Quick start:
  pip install fastapi uvicorn python-multipart
  API_KEY=secret uvicorn server:app --host 0.0.0.0 --port 8000
Open http://<server>:8000   (HTTPS, open source: caddy reverse-proxy --from map.example.com --to :8000)
New flight: curl -X DELETE -H "X-Api-Key: secret" http://<server>:8000/api/tiles
"""
import asyncio, json, os, pathlib, shutil
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

KEY = os.environ.get("API_KEY", "changeme")
DATA = pathlib.Path(os.environ.get("DATA_DIR", "data")); DATA.mkdir(exist_ok=True)
LOG = DATA / "tiles.jsonl"
tiles = [json.loads(l) for l in LOG.open()] if LOG.exists() else []
subs = set()
app = FastAPI()


def auth(k):
    if k != KEY:
        raise HTTPException(401, "bad key")


@app.post("/api/tile")
async def post_tile(meta: str = Form(...), rgb: UploadFile = File(...), ndvi: UploadFile = File(...),
                    ndre: UploadFile = File(...), x_api_key: str = Header(None)):
    auth(x_api_key)
    m = json.loads(meta)
    tid = tiles[-1]["id"] + 1 if tiles else 0
    for name, f in (("rgb", rgb), ("ndvi", ndvi), ("ndre", ndre)):
        (DATA / f"{tid}_{name}.webp").write_bytes(await f.read())
    rec = {"id": tid, "t": m.get("t"), "bounds": m["bounds"],
           "urls": {k: f"/tiles/{tid}_{k}.webp" for k in ("rgb", "ndvi", "ndre")}}
    tiles.append(rec)
    with LOG.open("a") as fh:
        fh.write(json.dumps(rec) + "\n")
    for q in list(subs):
        q.put_nowait(rec)
    return {"id": tid}


@app.get("/api/tiles")
def list_tiles():
    return tiles


@app.delete("/api/tiles")
def reset(x_api_key: str = Header(None)):
    auth(x_api_key)
    tiles.clear(); shutil.rmtree(DATA); DATA.mkdir()
    return {"ok": True}


@app.get("/api/stream")
async def stream():
    q = asyncio.Queue(); subs.add(q)

    async def gen():
        try:
            while True:
                try:
                    rec = await asyncio.wait_for(q.get(), 15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"; continue
                yield f"data: {json.dumps(rec)}\n\n"
        finally:
            subs.discard(q)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/")
def index():
    return FileResponse(pathlib.Path(__file__).parent / "index.html")


app.mount("/tiles", StaticFiles(directory=DATA))
