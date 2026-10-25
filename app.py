# app.py
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
        width: 100% !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

TILES_FILE = Path("static/tiles.json")
if not TILES_FILE.exists():
    st.error("Missing static/tiles.json! Please run 'python prepare_stream.py' first.")
    st.stop()

json_data = TILES_FILE.read_text(encoding="utf-8")

html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * {{
      box-sizing: border-box;
    }}
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #8b8b88;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    #app-container {{
      display: flex;
      flex-direction: column;
      width: 100%;
      height: 100vh;
      position: relative;
    }}
    #map {{
      flex: 1;
      width: 100%;
      background: #8b8b88;
    }}
    /* Docked Bottom Navigation Bar */
    #tab-bar {{
      height: 54px;
      min-height: 54px;
      width: 100%;
      background: #111111;
      display: flex;
      z-index: 2000;
      box-shadow: 0 -2px 10px rgba(0,0,0,0.6);
    }}
    .tab {{
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
    }}
    .tab:hover {{
      color: #ffffff;
      background: #191919;
    }}
    .tab.active {{
      color: #ffffff;
      background: #1e1e1e;
      border-top: 3px solid #4caf50;
    }}
    #counter {{
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
    }}
    #legend {{
      position: absolute;
      bottom: 66px;
      left: 14px;
      background: rgba(255, 255, 255, 0.95);
      padding: 8px 12px;
      border-radius: 4px;
      font-size: 11px;
      color: #111;
      z-index: 1000;
      box-shadow: 0 1px 4px rgba(0,0,0,0.3);
      display: block;
    }}
    .bar {{
      width: 140px;
      height: 10px;
      background: linear-gradient(to right, #000000, #ffffff);
      margin-bottom: 4px;
      border: 1px solid #777;
    }}
    .labels {{
      display: flex;
      justify-content: space-between;
      font-weight: bold;
    }}
  </style>
</head>
<body>
  <div id="app-container">
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
  </div>

  <script>
    const streamData = {json_data};
    const [imgH, imgW] = streamData.dimensions;
    const tiles = streamData.tiles;

    let currentMode = 'ndre';

    const layerGroups = {{
      'rgb': L.layerGroup(),
      'ndvi': L.layerGroup(),
      'ndre': L.layerGroup()
    }};

    const map = L.map('map', {{
      crs: L.CRS.Simple,
      minZoom: -3,
      maxZoom: 3,
      zoomControl: true,
      attributionControl: false
    }});

    const fullBounds = [[0, 0], [imgH, imgW]];
    map.fitBounds(fullBounds);

    layerGroups[currentMode].addTo(map);

    function switchLayer(mode) {{
      if (mode === currentMode) return;
      
      map.removeLayer(layerGroups[currentMode]);
      map.addLayer(layerGroups[mode]);
      currentMode = mode;

      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      const activeIdx = mode === 'rgb' ? 0 : (mode === 'ndvi' ? 1 : 2);
      document.querySelectorAll('.tab')[activeIdx].classList.add('active');

      const legend = document.getElementById('legend');
      const legMax = document.getElementById('leg-max');
      if (mode === 'rgb') {{
        legend.style.display = 'none';
      }} else {{
        legend.style.display = 'block';
        legMax.innerText = mode === 'ndvi' ? '1.0' : '0.6';
      }}
    }}

    let tileIndex = 0;
    const counterEl = document.getElementById('counter');

    function streamNextTile() {{
      if (tileIndex >= tiles.length) {{
        counterEl.innerText = `${{tiles.length}} tiles (Complete)`;
        return;
      }}

      const t = tiles[tileIndex];
      
      L.imageOverlay(t.rgb, t.bounds, {{ opacity: 0.95 }}).addTo(layerGroups['rgb']);
      L.imageOverlay(t.ndvi, t.bounds, {{ opacity: 0.95 }}).addTo(layerGroups['ndvi']);
      L.imageOverlay(t.ndre, t.bounds, {{ opacity: 0.95 }}).addTo(layerGroups['ndre']);

      tileIndex++;
      counterEl.innerText = `${{tileIndex}} tiles`;

      setTimeout(streamNextTile, 300);
    }}

    streamNextTile();
  </script>
</body>
</html>
"""

components.html(html_content, height=920, scrolling=False)