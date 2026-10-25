import json
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Crop Map Visualizer",
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
      }
    </style>
    """,
    unsafe_allow_html=True,
)

TILES_FILE = Path("static/tiles.json")
if not TILES_FILE.exists():
    st.error("static/tiles.json not found! Run python generate_layers.py first.")
    st.stop()

with open(TILES_FILE, "r") as f:
    mosaic_data = f.read()

html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100vh;
      overflow: hidden;
      background: #8b8b88;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    #map {{
      width: 100%;
      height: calc(100vh - 54px);
      background: #8b8b88;
    }}
    #tab-bar {{
      height: 54px;
      width: 100%;
      background: #111;
      display: flex;
      box-shadow: 0 -2px 10px rgba(0,0,0,0.5);
    }}
    .tab {{
      flex: 1;
      color: #999;
      font-size: 16px;
      font-weight: 600;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      user-select: none;
      border-top: 3px solid transparent;
      transition: all 0.15s ease;
    }}
    .tab:hover {{
      color: #eee;
    }}
    .tab.active {{
      color: #fff;
      background: #1a1a1a;
      border-top: 3px solid #4caf50;
    }}
    #counter {{
      position: absolute;
      top: 14px;
      right: 14px;
      background: rgba(255, 255, 255, 0.9);
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
    const data = {mosaic_data};
    const totalTiles = data.tiles.length;
    let currentMode = 'ndre';
    let currentTileIdx = 0;

    // Three Layer Groups running in parallel
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

    // Center the map on image bounds
    const fullBounds = [[0, 0], [data.height, data.width]];
    map.fitBounds(fullBounds);

    // Add active layer group to map
    layerGroups[currentMode].addTo(map);

    // Incremental Stream Loop (1 tile every 400ms)
    function streamNextTile() {{
      if (currentTileIdx >= totalTiles) return;

      const tile = data.tiles[currentTileIdx];
      // Invert Y coordinate so [0,0] is top-left
      const b = [
        [data.height - tile.bounds[1][0], tile.bounds[0][1]],
        [data.height - tile.bounds[0][0], tile.bounds[1][1]]
      ];

      // Add tile to ALL 3 layer groups at the exact same time
      L.imageOverlay(tile.urls['rgb'], b, {{ opacity: 0.95 }}).addTo(layerGroups['rgb']);
      L.imageOverlay(tile.urls['ndvi'], b, {{ opacity: 0.95 }}).addTo(layerGroups['ndvi']);
      L.imageOverlay(tile.urls['ndre'], b, {{ opacity: 0.95 }}).addTo(layerGroups['ndre']);

      currentTileIdx++;
      document.getElementById('counter').innerText = `${{currentTileIdx}} / ${{totalTiles}} tiles`;

      setTimeout(streamNextTile, 400);
    }}

    // Tab Switching
    function switchLayer(mode) {{
      if (mode === currentMode) return;

      // Swap displayed layer group
      map.removeLayer(layerGroups[currentMode]);
      layerGroups[mode].addTo(map);
      currentMode = mode;

      // Update Tab Styles
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      const activeIdx = mode === 'rgb' ? 0 : (mode === 'ndvi' ? 1 : 2);
      document.querySelectorAll('.tab')[activeIdx].classList.add('active');

      // Update Legend
      const legend = document.getElementById('legend');
      const legMax = document.getElementById('leg-max');
      if (mode === 'rgb') {{
        legend.style.display = 'none';
      }} else {{
        legend.style.display = 'block';
        legMax.innerText = mode === 'ndvi' ? '1.0' : '0.6';
      }}
    }}

    // Start streaming
    streamNextTile();
  </script>
</body>
</html>
"""

components.html(html_content, height=850, scrolling=False)