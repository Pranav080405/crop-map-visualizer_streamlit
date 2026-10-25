# app.py
import base64
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Crop Map Live Stream",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      #MainMenu, header, footer {visibility: hidden;}
      .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
      }
      iframe {
        border: none;
        width: 100vw !important;
        height: 100vh !important;
        display: block;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

TILES_FILE = Path("static/tiles.json")
if not TILES_FILE.exists():
    st.error("Missing static/tiles.json! Please verify the file is committed to your repository.")
    st.stop()

tiles_b64 = base64.b64encode(TILES_FILE.read_bytes()).decode("utf-8")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden !important;
      background: #8b8b88;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    #map {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 54px;
      width: 100%;
      background: #8b8b88;
    }
    /* Fixed Docked Bottom Navigation Bar */
    #tab-bar {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: 54px;
      background: #111111;
      display: flex;
      z-index: 9999;
      box-shadow: 0 -2px 10px rgba(0,0,0,0.6);
    }
    .tab {
      flex: 1;
      color: #888888;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.8px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      user-select: none;
      border-top: 3px solid transparent;
      transition: background 0.2s, color 0.2s, border 0.2s;
    }
    .tab:hover { color: #ffffff; background: #191919; }
    .tab.active {
      color: #ffffff;
      background: #1e1e1e;
      border-top: 3px solid #4caf50;
    }
    #counter {
      position: absolute;
      top: 14px;
      right: 14px;
      background: rgba(255, 255, 255, 0.95);
      padding: 6px 14px;
      border-radius: 4px;
      font-size: 13px;
      font-weight: bold;
      color: #222;
      z-index: 1000;
      box-shadow: 0 1px 4px rgba(0,0,0,0.3);
    }
    #legend {
      position: absolute;
      bottom: 68px;
      left: 14px;
      background: rgba(255, 255, 255, 0.95);
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 11px;
      color: #111;
      z-index: 1000;
      box-shadow: 0 1px 4px rgba(0,0,0,0.3);
      display: block;
    }
    .bar {
      width: 140px;
      height: 10px;
      background: linear-gradient(to right, #000000, #ffffff);
      margin-bottom: 4px;
      border: 1px solid #777;
    }
    .labels {
      display: flex;
      justify-content: space-between;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <div id="counter">0 tiles</div>
  <div id="map"></div>
  <div id="legend">
    <div class="bar"></div>
    <div class="labels"><span id="leg-min">0</span><span id="leg-max">0.6</span></div>
  </div>
  <div id="tab-bar">
    <div class="tab" onclick="switchLayer('rgb')">RGB</div>
    <div class="tab" onclick="switchLayer('ndvi')">NDVI</div>
    <div class="tab active" onclick="switchLayer('ndre')">NDRE</div>
  </div>

  <script>
    const counterEl = document.getElementById('counter');
    let currentMode = 'ndre';

    const layerGroups = {
      'rgb': L.layerGroup(),
      'ndvi': L.layerGroup(),
      'ndre': L.layerGroup()
    };

    // CRS with [0,0] at top-left matching image pixel arrays
    const crsTopLeft = L.Util.extend({}, L.CRS.Simple, {
      transformation: new L.Transformation(1, 0, 1, 0)
    });

    const map = L.map('map', {
      crs: crsTopLeft,
      minZoom: -4,
      maxZoom: 4,
      zoomControl: true,
      attributionControl: false
    });

    layerGroups[currentMode].addTo(map);

    function switchLayer(mode) {
      if (mode === currentMode) return;
      map.removeLayer(layerGroups[currentMode]);
      map.addLayer(layerGroups[mode]);
      currentMode = mode;

      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      const activeIdx = mode === 'rgb' ? 0 : (mode === 'ndvi' ? 1 : 2);
      document.querySelectorAll('.tab')[activeIdx].classList.add('active');

      const legend = document.getElementById('legend');
      const legMax = document.getElementById('leg-max');
      if (mode === 'rgb') {
        legend.style.display = 'none';
      } else {
        legend.style.display = 'block';
        legMax.innerText = mode === 'ndvi' ? '1.0' : '0.6';
      }
    }

    try {
      const binaryString = atob("__TILES_B64__");
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const decodedJson = new TextDecoder('utf-8').decode(bytes);
      const parsed = JSON.parse(decodedJson);

      const tiles = Array.isArray(parsed) ? parsed : (parsed.tiles || []);
      const [imgH, imgW] = parsed.dimensions || [1000, 1000];

      if (!tiles.length) {
        counterEl.innerText = "No tiles found in JSON";
        throw new Error("No tiles in parsed JSON");
      }

      // Exact pixel bounds
      map.fitBounds([[0, 0], [imgH, imgW]]);

      let tileIndex = 0;
      function streamNextTile() {
        if (tileIndex >= tiles.length) {
          counterEl.innerText = tiles.length + " tiles (Complete)";
          return;
        }

        const t = tiles[tileIndex];
        const rgbImg = t.rgb || (t.urls && t.urls.rgb);
        const ndviImg = t.ndvi || (t.urls && t.urls.ndvi);
        const ndreImg = t.ndre || (t.urls && t.urls.ndre);

        if (rgbImg) L.imageOverlay(rgbImg, t.bounds, { opacity: 0.98, interactive: false }).addTo(layerGroups['rgb']);
        if (ndviImg) L.imageOverlay(ndviImg, t.bounds, { opacity: 0.98, interactive: false }).addTo(layerGroups['ndvi']);
        if (ndreImg) L.imageOverlay(ndreImg, t.bounds, { opacity: 0.98, interactive: false }).addTo(layerGroups['ndre']);

        tileIndex++;
        counterEl.innerText = tileIndex + " / " + tiles.length + " tiles";

        setTimeout(streamNextTile, 150);
      }

      streamNextTile();
    } catch (err) {
      console.error(err);
      counterEl.innerText = "Error parsing tiles: " + err.message;
    }
  </script>
</body>
</html>
"""

html_content = HTML_TEMPLATE.replace("__TILES_B64__", tiles_b64)
components.html(html_content, height=850, scrolling=False)