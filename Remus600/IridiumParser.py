"""
Title: Iridium SBD Message Parser and Map Viewer
Author: Mike Bollinger
Last Updated: 2026-07-01

FUNCTION:
    Parses REMUS/Iridium Short Burst Data (SBD) status messages (message
    number, battery voltages, GPS time/position/fix quality, geo x/y/z) and
    serves a local web page that lists parsed fields and plots the position
    on a map tile viewer.

USAGE:
    Run the script to start a local HTTP server and open the viewer in your
    default browser:
        python IridiumParser.py
    Paste one or more raw Iridium SBD message strings into the web page to
    parse and plot them.

INPUTS:
    - Raw Iridium SBD message text pasted into the web UI, matching the
      format: "<msg#> <status> <main batt> <emerg batt> <time>,<lat>,<N/S>,
      <lon>,<E/W>,<fix quality>,<satellites> <geo_x> <geo_y> <geo_z> ...".

OUTPUTS:
    An interactive local web page (served over HTTP, opened in the browser)
    showing parsed message fields in a table and plotted positions on a map.
    No files are written to disk.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import geopandas as gpd


MESSAGE_PATTERN = re.compile(
	r"^\s*"
	r"(?P<message_number>\d{3})\s+"
	r"(?P<supervisor_status>\d+)\s+"
	r"(?P<main_battery_voltage>-?\d+(?:\.\d+)?)\s+"
	r"(?P<emergency_battery_voltage>-?\d+(?:\.\d+)?)\s+"
	r"(?P<time>\d+(?:\.\d+)?),"
	r"(?P<latitude>\d+(?:\.\d+)?),(?P<latitude_hemisphere>[NS]),"
	r"(?P<longitude>\d+(?:\.\d+)?),(?P<longitude_hemisphere>[EW]),"
	r"(?P<gps_fix_quality>\d+),"
	r"(?P<gps_satellites>\d+)\s+"
	r"(?P<geo_x>-?\d+)\s+"
	r"(?P<geo_y>-?\d+)\s+"
	r"(?P<geo_z>-?\d+)"
	r"(?:\s+(?P<remainder>.*?))?"
	r"\s*$"
)

BOUNDARY_SHAPEFILE = (
	Path(__file__).resolve().parents[1]
	/ "VehicleGISTools"
	/ "NorthAmerica_Boundaries"
	/ "boundaries_p_2021_v3.shp"
)

ONLINE_TILE_URL = "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}"
ONLINE_TEST_URL = ONLINE_TILE_URL.format(x=0, y=0, z=1)
SAMPLE_MESSAGE = (
	"000 40 27.96 17.75 211525.00,4131.4480820,N,07040.2951950,W,1,06  "
	"1580 -4512  4204 C803E49F 0000 0000 0000 0000 0000 0000 0000 0000"
)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Iridium Message Parser</title>
  <style>
    :root {
      --bg: #f3efe4;
      --panel: rgba(255, 252, 246, 0.94);
      --ink: #162024;
      --muted: #617176;
      --line: #d4ccb9;
      --accent: #b14d2c;
      --accent-dark: #7f3117;
      --map-bg: #dbe7ef;
      --success: #355d4c;
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(177, 77, 44, 0.12), transparent 34%),
        radial-gradient(circle at bottom right, rgba(22, 32, 36, 0.10), transparent 30%),
        linear-gradient(145deg, #efe7d6, var(--bg));
      color: var(--ink);
    }

    .app {
      display: grid;
      grid-template-columns: minmax(360px, 440px) minmax(520px, 1fr);
      gap: 18px;
      min-height: 100vh;
      padding: 18px;
    }

    .panel {
      background: var(--panel);
      border: 1px solid rgba(97, 113, 118, 0.18);
      border-radius: 18px;
      box-shadow: 0 18px 48px rgba(22, 32, 36, 0.10);
      backdrop-filter: blur(10px);
    }

    .left-panel {
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .header {
      padding: 22px 22px 10px;
    }

    .eyebrow {
      display: inline-block;
      margin-bottom: 10px;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(177, 77, 44, 0.12);
      color: var(--accent-dark);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 30px;
      line-height: 1.1;
    }

    .subtitle {
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }

    .input-wrap {
      padding: 0 22px 18px;
    }

    textarea {
      width: 100%;
      min-height: 148px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      font: 14px/1.5 Consolas, "Courier New", monospace;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.82);
    }

    textarea:focus {
      outline: 2px solid rgba(177, 77, 44, 0.22);
      border-color: rgba(177, 77, 44, 0.45);
    }

    .button-row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 14px;
    }

    button {
      border: 0;
      border-radius: 12px;
      padding: 11px 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      transition: transform 120ms ease, opacity 120ms ease, box-shadow 120ms ease;
    }

    button:hover {
      transform: translateY(-1px);
    }

    button:active {
      transform: translateY(0);
    }

    .primary {
      background: var(--accent);
      color: white;
      box-shadow: 0 10px 20px rgba(177, 77, 44, 0.24);
    }

    .secondary {
      background: rgba(255, 255, 255, 0.86);
      color: var(--ink);
      border: 1px solid rgba(97, 113, 118, 0.25);
    }

    .status {
      padding: 0 22px 14px;
      color: var(--success);
      font-size: 14px;
      min-height: 22px;
    }

    .error {
      color: #9f2d20;
    }

    .table-wrap {
      padding: 0 22px 22px;
      overflow: auto;
      flex: 1;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      border-spacing: 0;
      overflow: hidden;
      border-radius: 14px;
      border: 1px solid rgba(97, 113, 118, 0.16);
      background: rgba(255, 255, 255, 0.7);
    }

    th, td {
      padding: 12px 14px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid rgba(97, 113, 118, 0.12);
    }

    th {
      width: 42%;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      background: rgba(22, 32, 36, 0.03);
    }

    tr:last-child th, tr:last-child td {
      border-bottom: 0;
    }

    .map-panel {
      display: flex;
      flex-direction: column;
      overflow: hidden;
      min-height: 720px;
    }

    .map-toolbar {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 18px 18px 10px;
    }

    .map-title {
      font-size: 20px;
      font-weight: 700;
    }

    .map-subtitle {
      color: var(--muted);
      font-size: 13px;
      margin-top: 4px;
    }

    .map-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .map-frame {
      position: relative;
      margin: 0 18px 18px;
      flex: 1;
      min-height: 620px;
      border-radius: 18px;
      overflow: hidden;
      background: var(--map-bg);
      border: 1px solid rgba(97, 113, 118, 0.18);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
      user-select: none;
      touch-action: none;
    }

    .tile-layer,
    .overlay-layer,
    .offline-canvas,
    .map-message {
      position: absolute;
      inset: 0;
    }

    .tile-layer img {
      position: absolute;
      width: 256px;
      height: 256px;
      image-rendering: auto;
      -webkit-user-drag: none;
    }

    .offline-canvas {
      width: 100%;
      height: 100%;
      display: none;
    }

    .marker {
      position: absolute;
      width: 18px;
      height: 18px;
      margin-left: -9px;
      margin-top: -9px;
      border-radius: 50%;
      background: #e04728;
      border: 3px solid white;
      box-shadow: 0 8px 18px rgba(0, 0, 0, 0.28);
      display: none;
    }

    .marker::after {
      content: "";
      position: absolute;
      inset: -9px;
      border-radius: 50%;
      border: 1px solid rgba(224, 71, 40, 0.35);
    }

    .map-message {
      display: grid;
      place-items: center;
      color: var(--muted);
      text-align: center;
      padding: 24px;
      font-size: 16px;
      background: linear-gradient(180deg, rgba(255,255,255,0.26), rgba(255,255,255,0.06));
    }

    .legend {
      position: absolute;
      left: 16px;
      bottom: 16px;
      padding: 10px 12px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.86);
      border: 1px solid rgba(97, 113, 118, 0.18);
      font-size: 12px;
      color: var(--muted);
      backdrop-filter: blur(8px);
    }

    .legend strong {
      color: var(--ink);
      display: block;
      margin-bottom: 4px;
    }

    @media (max-width: 1080px) {
      .app {
        grid-template-columns: 1fr;
      }

      .map-panel {
        min-height: 560px;
      }

      .map-frame {
        min-height: 480px;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <section class="panel left-panel">
      <div class="header">
        <span class="eyebrow">Local Web App</span>
        <h1>Iridium Message Parser</h1>
        <p class="subtitle">Paste an AUV Iridium message, parse the fields, and inspect the vehicle location on an interactive map.</p>
      </div>
      <div class="input-wrap">
        <textarea id="messageInput" spellcheck="false"></textarea>
        <div class="button-row">
          <button class="primary" id="parseButton">Parse Message</button>
          <button class="secondary" id="sampleButton">Load Sample</button>
          <button class="secondary" id="clearButton">Clear</button>
        </div>
      </div>
      <div class="status" id="statusText"></div>
      <div class="table-wrap">
        <table>
          <tbody id="resultsBody">
            <tr>
              <th>Results</th>
              <td>Parse a message to populate the decoded fields.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel map-panel">
      <div class="map-toolbar">
        <div>
          <div class="map-title">Vehicle Position</div>
          <div class="map-subtitle" id="mapStatus">Map waiting for parsed coordinates.</div>
        </div>
        <div class="map-actions">
          <button class="secondary" id="zoomOutButton">Zoom Out</button>
          <button class="secondary" id="zoomInButton">Zoom In</button>
          <button class="secondary" id="recenterButton">Recenter</button>
        </div>
      </div>
      <div class="map-frame" id="mapFrame">
        <div class="tile-layer" id="tileLayer"></div>
        <canvas class="offline-canvas" id="offlineCanvas"></canvas>
        <div class="overlay-layer">
          <div class="marker" id="marker"></div>
        </div>
        <div class="map-message" id="mapMessage">Parse a message to show the vehicle location.</div>
        <div class="legend">
          <strong>Controls</strong>
          Drag to pan. Use the mouse wheel or zoom buttons to change scale.
        </div>
      </div>
    </section>
  </div>

  <script>
    const SAMPLE_MESSAGE = __SAMPLE_JSON__;
    const TILE_URL_TEMPLATE = __TILE_URL_JSON__;
    const state = {
      parsed: null,
      online: null,
      onlineZoom: 7,
      onlineCenter: null,
      offlineCenter: null,
      offlineLonSpan: 60,
      boundaries: null,
      dragging: false,
      dragOrigin: null,
      dragStartCenter: null,
      dragStartSpan: null
    };

    const messageInput = document.getElementById('messageInput');
    const resultsBody = document.getElementById('resultsBody');
    const statusText = document.getElementById('statusText');
    const mapStatus = document.getElementById('mapStatus');
    const mapFrame = document.getElementById('mapFrame');
    const mapMessage = document.getElementById('mapMessage');
    const tileLayer = document.getElementById('tileLayer');
    const marker = document.getElementById('marker');
    const offlineCanvas = document.getElementById('offlineCanvas');

    function setStatus(message, isError = false) {
      statusText.textContent = message;
      statusText.classList.toggle('error', isError);
    }

    function setMapStatus(message) {
      mapStatus.textContent = message;
    }

    function showMapMessage(message) {
      mapMessage.textContent = message;
      mapMessage.style.display = 'grid';
    }

    function hideMapMessage() {
      mapMessage.style.display = 'none';
    }

    function renderResults(rows) {
      resultsBody.innerHTML = '';
      for (const row of rows) {
        const tr = document.createElement('tr');
        const th = document.createElement('th');
        const td = document.createElement('td');
        th.textContent = row.field;
        td.textContent = row.value;
        tr.appendChild(th);
        tr.appendChild(td);
        resultsBody.appendChild(tr);
      }
    }

    function clearResults() {
      resultsBody.innerHTML = '';
      const tr = document.createElement('tr');
      const th = document.createElement('th');
      const td = document.createElement('td');
      th.textContent = 'Results';
      td.textContent = 'Parse a message to populate the decoded fields.';
      tr.appendChild(th);
      tr.appendChild(td);
      resultsBody.appendChild(tr);
    }

    function lngLatToWorld(lng, lat, zoom) {
      const sinLat = Math.sin(lat * Math.PI / 180);
      const scale = 256 * Math.pow(2, zoom);
      const x = (lng + 180) / 360 * scale;
      const y = (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * scale;
      return { x, y };
    }

    function worldToLngLat(x, y, zoom) {
      const scale = 256 * Math.pow(2, zoom);
      const lng = x / scale * 360 - 180;
      const n = Math.PI - 2 * Math.PI * y / scale;
      const lat = 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
      return { lng, lat };
    }

    function normalizeTileX(x, zoom) {
      const tiles = Math.pow(2, zoom);
      return ((x % tiles) + tiles) % tiles;
    }

    function recenterOnline() {
      if (!state.parsed) {
        return;
      }
      state.onlineCenter = {
        lat: state.parsed.latitude_decimal_degrees,
        lng: state.parsed.longitude_decimal_degrees
      };
      if (!state.onlineZoom) {
        state.onlineZoom = 7;
      }
    }

    function recenterOffline() {
      if (!state.parsed) {
        return;
      }
      state.offlineCenter = {
        lat: state.parsed.latitude_decimal_degrees,
        lng: state.parsed.longitude_decimal_degrees
      };
      state.offlineLonSpan = 16;
    }

    function renderOnlineMap() {
      if (!state.parsed || !state.onlineCenter) {
        showMapMessage('Parse a message to show the vehicle location.');
        return;
      }

      hideMapMessage();
      offlineCanvas.style.display = 'none';
      tileLayer.style.display = 'block';
      marker.style.display = 'block';

      const width = mapFrame.clientWidth;
      const height = mapFrame.clientHeight;
      const zoom = state.onlineZoom;
      const centerWorld = lngLatToWorld(state.onlineCenter.lng, state.onlineCenter.lat, zoom);
      const topLeftX = centerWorld.x - width / 2;
      const topLeftY = centerWorld.y - height / 2;
      const startTileX = Math.floor(topLeftX / 256);
      const startTileY = Math.floor(topLeftY / 256);
      const endTileX = Math.floor((topLeftX + width) / 256);
      const endTileY = Math.floor((topLeftY + height) / 256);
      const maxY = Math.pow(2, zoom) - 1;

      tileLayer.innerHTML = '';
      const fragment = document.createDocumentFragment();
      for (let tileX = startTileX; tileX <= endTileX; tileX += 1) {
        for (let tileY = startTileY; tileY <= endTileY; tileY += 1) {
          if (tileY < 0 || tileY > maxY) {
            continue;
          }
          const img = document.createElement('img');
          img.alt = '';
          img.draggable = false;
          img.src = TILE_URL_TEMPLATE
            .replace('{x}', normalizeTileX(tileX, zoom))
            .replace('{y}', tileY)
            .replace('{z}', zoom);
          img.style.left = `${tileX * 256 - topLeftX}px`;
          img.style.top = `${tileY * 256 - topLeftY}px`;
          fragment.appendChild(img);
        }
      }
      tileLayer.appendChild(fragment);

      const pointWorld = lngLatToWorld(
        state.parsed.longitude_decimal_degrees,
        state.parsed.latitude_decimal_degrees,
        zoom
      );
      marker.style.left = `${pointWorld.x - topLeftX}px`;
      marker.style.top = `${pointWorld.y - topLeftY}px`;
      setMapStatus(`Online basemap. Zoom ${zoom}.`);
    }

    function getOfflineBounds() {
      if (!state.boundaries) {
        return null;
      }
      return state.boundaries.bounds;
    }

    function ensureOfflineBoundaries() {
      if (state.boundaries) {
        return Promise.resolve(state.boundaries);
      }

      return fetch('/api/boundaries')
        .then(response => response.json())
        .then(data => {
          state.boundaries = data;
          return data;
        });
    }

    function drawPolygonRing(context, ring, project) {
      if (!ring.length) {
        return;
      }
      context.beginPath();
      ring.forEach((coord, index) => {
        const [x, y] = project(coord[0], coord[1]);
        if (index === 0) {
          context.moveTo(x, y);
        } else {
          context.lineTo(x, y);
        }
      });
      context.closePath();
      context.fill();
      context.stroke();
    }

    function renderOfflineMap() {
      if (!state.parsed || !state.offlineCenter || !state.boundaries) {
        showMapMessage('Offline basemap is loading.');
        return;
      }

      hideMapMessage();
      tileLayer.style.display = 'none';
      marker.style.display = 'none';
      offlineCanvas.style.display = 'block';

      const rect = mapFrame.getBoundingClientRect();
      const width = Math.max(1, Math.floor(rect.width));
      const height = Math.max(1, Math.floor(rect.height));
      offlineCanvas.width = width;
      offlineCanvas.height = height;
      const context = offlineCanvas.getContext('2d');
      context.clearRect(0, 0, width, height);
      context.fillStyle = '#dbe7ef';
      context.fillRect(0, 0, width, height);

      const lonSpan = state.offlineLonSpan;
      const latSpan = lonSpan * (height / width);
      const centerLon = state.offlineCenter.lng;
      const centerLat = state.offlineCenter.lat;
      const minLon = centerLon - lonSpan / 2;
      const maxLon = centerLon + lonSpan / 2;
      const minLat = centerLat - latSpan / 2;
      const maxLat = centerLat + latSpan / 2;

      const project = (lng, lat) => {
        const x = ((lng - minLon) / (maxLon - minLon)) * width;
        const y = ((maxLat - lat) / (maxLat - minLat)) * height;
        return [x, y];
      };

      context.fillStyle = '#eef3e7';
      context.strokeStyle = '#60735c';
      context.lineWidth = 1;

      for (const feature of state.boundaries.geojson.features) {
        const geometry = feature.geometry;
        if (!geometry) {
          continue;
        }
        if (geometry.type === 'Polygon') {
          for (const ring of geometry.coordinates) {
            drawPolygonRing(context, ring, project);
          }
        }
        if (geometry.type === 'MultiPolygon') {
          for (const polygon of geometry.coordinates) {
            for (const ring of polygon) {
              drawPolygonRing(context, ring, project);
            }
          }
        }
      }

      const point = project(
        state.parsed.longitude_decimal_degrees,
        state.parsed.latitude_decimal_degrees
      );
      context.fillStyle = '#e04728';
      context.strokeStyle = '#ffffff';
      context.lineWidth = 3;
      context.beginPath();
      context.arc(point[0], point[1], 8, 0, Math.PI * 2);
      context.fill();
      context.stroke();

      setMapStatus('Offline shapefile basemap.');
    }

    function renderMap() {
      if (!state.parsed) {
        showMapMessage('Parse a message to show the vehicle location.');
        return;
      }

      if (state.online) {
        renderOnlineMap();
        return;
      }

      ensureOfflineBoundaries()
        .then(() => {
          renderOfflineMap();
        })
        .catch(() => {
          showMapMessage('Failed to load the offline boundary layer.');
          setMapStatus('Offline boundary layer failed to load.');
        });
    }

    function parseMessage() {
      const message = messageInput.value.trim();
      if (!message) {
        setStatus('Paste an Iridium message to parse.', true);
        return;
      }

      setStatus('Parsing message...');
      fetch('/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      })
        .then(async response => {
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.error || 'Parse failed.');
          }
          return data;
        })
        .then(data => {
          state.parsed = data;
          state.online = data.online;
          recenterOnline();
          recenterOffline();
          renderResults(data.rows);
          setStatus(`Parsed successfully. Map mode: ${data.online ? 'online tiles' : 'offline shapefile'}.`);
          renderMap();
        })
        .catch(error => {
          setStatus(error.message, true);
        });
    }

    function clearAll() {
      messageInput.value = '';
      state.parsed = null;
      state.online = null;
      tileLayer.innerHTML = '';
      marker.style.display = 'none';
      offlineCanvas.style.display = 'none';
      clearResults();
      setStatus('');
      setMapStatus('Map waiting for parsed coordinates.');
      showMapMessage('Parse a message to show the vehicle location.');
    }

    function zoomMap(delta) {
      if (!state.parsed) {
        return;
      }

      if (state.online) {
        state.onlineZoom = Math.max(2, Math.min(18, state.onlineZoom + delta));
        renderOnlineMap();
        return;
      }

      state.offlineLonSpan = Math.max(0.05, Math.min(180, state.offlineLonSpan * (delta > 0 ? 0.8 : 1.25)));
      renderOfflineMap();
    }

    function recenterMap() {
      if (!state.parsed) {
        return;
      }
      recenterOnline();
      recenterOffline();
      renderMap();
    }

    function startDrag(event) {
      if (!state.parsed) {
        return;
      }
      state.dragging = true;
      state.dragOrigin = { x: event.clientX, y: event.clientY };
      state.dragStartCenter = state.online
        ? { ...state.onlineCenter }
        : { ...state.offlineCenter };
      state.dragStartSpan = state.offlineLonSpan;
      mapFrame.style.cursor = 'grabbing';
    }

    function moveDrag(event) {
      if (!state.dragging || !state.parsed) {
        return;
      }

      const dx = event.clientX - state.dragOrigin.x;
      const dy = event.clientY - state.dragOrigin.y;
      const width = mapFrame.clientWidth;
      const height = mapFrame.clientHeight;

      if (state.online) {
        const world = lngLatToWorld(state.dragStartCenter.lng, state.dragStartCenter.lat, state.onlineZoom);
        const moved = worldToLngLat(world.x - dx, world.y - dy, state.onlineZoom);
        state.onlineCenter = { lat: moved.lat, lng: moved.lng };
        renderOnlineMap();
        return;
      }

      const lonSpan = state.dragStartSpan;
      const latSpan = lonSpan * (height / width);
      state.offlineCenter = {
        lng: state.dragStartCenter.lng - (dx / width) * lonSpan,
        lat: state.dragStartCenter.lat + (dy / height) * latSpan
      };
      renderOfflineMap();
    }

    function endDrag() {
      state.dragging = false;
      mapFrame.style.cursor = 'grab';
    }

    document.getElementById('parseButton').addEventListener('click', parseMessage);
    document.getElementById('sampleButton').addEventListener('click', () => {
      messageInput.value = SAMPLE_MESSAGE;
      setStatus('Sample message loaded.');
    });
    document.getElementById('clearButton').addEventListener('click', clearAll);
    document.getElementById('zoomInButton').addEventListener('click', () => zoomMap(1));
    document.getElementById('zoomOutButton').addEventListener('click', () => zoomMap(-1));
    document.getElementById('recenterButton').addEventListener('click', recenterMap);
    mapFrame.addEventListener('mousedown', startDrag);
    window.addEventListener('mousemove', moveDrag);
    window.addEventListener('mouseup', endDrag);
    mapFrame.addEventListener('mouseleave', endDrag);
    mapFrame.addEventListener('wheel', event => {
      event.preventDefault();
      zoomMap(event.deltaY < 0 ? 1 : -1);
    }, { passive: false });
    window.addEventListener('resize', () => {
      if (state.parsed) {
        renderMap();
      }
    });

    messageInput.value = SAMPLE_MESSAGE;
    setStatus('Sample message loaded.');
    mapFrame.style.cursor = 'grab';
  </script>
</body>
</html>
"""


@dataclass
class ParsedCoordinate:
	raw_decimal_minutes: str
	hemisphere: str
	degrees: int
	degree_width: int
	decimal_minutes: float
	decimal_degrees: float

	@property
	def decimal_minutes_display(self) -> str:
		return (
			f"{self.degrees:0{self.degree_width}d}\N{DEGREE SIGN} "
			f"{self.decimal_minutes:.6f}' {self.hemisphere}"
		)

	@property
	def decimal_degrees_display(self) -> str:
		return f"{self.decimal_degrees:.8f}\N{DEGREE SIGN}"


@dataclass
class ParsedIridiumMessage:
	message_number: str
	supervisor_status: str
	main_battery_voltage: float
	emergency_battery_voltage: float
	time_utc: str
	latitude: ParsedCoordinate
	longitude: ParsedCoordinate
	gps_fix_quality: str
	gps_satellites: int
	iridium_geolocation: str
	remainder: str


def parse_decimal_minutes(raw_value: str, hemisphere: str) -> ParsedCoordinate:
	if hemisphere not in {"N", "S", "E", "W"}:
		raise ValueError(f"Unsupported hemisphere: {hemisphere}")

	degree_digits = 2 if hemisphere in {"N", "S"} else 3
	degrees = int(raw_value[:degree_digits])
	decimal_minutes = float(raw_value[degree_digits:])
	decimal_degrees = degrees + (decimal_minutes / 60.0)

	if hemisphere in {"S", "W"}:
		decimal_degrees *= -1

	return ParsedCoordinate(
		raw_decimal_minutes=raw_value,
		hemisphere=hemisphere,
		degrees=degrees,
		degree_width=degree_digits,
		decimal_minutes=decimal_minutes,
		decimal_degrees=decimal_degrees,
	)


def parse_iridium_message(message: str) -> ParsedIridiumMessage:
	cleaned_message = " ".join(message.strip().split())
	match = MESSAGE_PATTERN.match(cleaned_message)
	if not match:
		raise ValueError(
			"Message format was not recognized. Verify the pasted Iridium string is complete."
		)

	groups = match.groupdict(default="")
	latitude = parse_decimal_minutes(groups["latitude"], groups["latitude_hemisphere"])
	longitude = parse_decimal_minutes(groups["longitude"], groups["longitude_hemisphere"])

	return ParsedIridiumMessage(
		message_number=groups["message_number"],
		supervisor_status=groups["supervisor_status"],
		main_battery_voltage=float(groups["main_battery_voltage"]),
		emergency_battery_voltage=float(groups["emergency_battery_voltage"]),
		time_utc=groups["time"],
		latitude=latitude,
		longitude=longitude,
		gps_fix_quality=groups["gps_fix_quality"],
		gps_satellites=int(groups["gps_satellites"]),
		iridium_geolocation=f"{groups['geo_x']} {groups['geo_y']} {groups['geo_z']}",
		remainder=groups["remainder"],
	)


def is_online() -> bool:
	try:
		with urlopen(ONLINE_TEST_URL, timeout=3) as response:
			return response.status == 200
	except OSError:
		return False


@lru_cache(maxsize=1)
def load_boundary_geojson() -> dict:
	gdf = gpd.read_file(BOUNDARY_SHAPEFILE)
	geojson = json.loads(gdf.to_crs("EPSG:4326").to_json())
	bounds = gdf.to_crs("EPSG:4326").total_bounds.tolist()
	return {"geojson": geojson, "bounds": bounds}


def parsed_message_to_rows(parsed: ParsedIridiumMessage) -> list[dict[str, str]]:
	return [
		{"field": "Emergency Message Number", "value": parsed.message_number},
		{"field": "Supervisor Status", "value": parsed.supervisor_status},
		{"field": "Main Battery Voltage", "value": f"{parsed.main_battery_voltage:.2f} V"},
		{
			"field": "Emergency Battery Voltage",
			"value": f"{parsed.emergency_battery_voltage:.2f} V",
		},
		{"field": "Time", "value": parsed.time_utc},
		{
			"field": "Latitude (Decimal Minutes)",
			"value": parsed.latitude.decimal_minutes_display,
		},
		{
			"field": "Latitude (Decimal Degrees)",
			"value": parsed.latitude.decimal_degrees_display,
		},
		{
			"field": "Longitude (Decimal Minutes)",
			"value": parsed.longitude.decimal_minutes_display,
		},
		{
			"field": "Longitude (Decimal Degrees)",
			"value": parsed.longitude.decimal_degrees_display,
		},
		{"field": "GPS Fix Quality", "value": parsed.gps_fix_quality},
		{"field": "GPS Satellites", "value": str(parsed.gps_satellites)},
		{"field": "Iridium Geolocation Fix", "value": parsed.iridium_geolocation},
		{"field": "Remaining Payload", "value": parsed.remainder or "<none>"},
	]


def serialize_parsed_message(parsed: ParsedIridiumMessage) -> dict:
	payload = asdict(parsed)
	payload["latitude_decimal_degrees"] = parsed.latitude.decimal_degrees
	payload["longitude_decimal_degrees"] = parsed.longitude.decimal_degrees
	payload["rows"] = parsed_message_to_rows(parsed)
	payload["online"] = is_online()
	return payload


def render_index_html() -> str:
	return (
		HTML_TEMPLATE.replace("__SAMPLE_JSON__", json.dumps(SAMPLE_MESSAGE))
		.replace("__TILE_URL_JSON__", json.dumps(ONLINE_TILE_URL))
	)


class IridiumRequestHandler(BaseHTTPRequestHandler):
	def do_GET(self) -> None:
		path = self.path.split("?", 1)[0]
		if path == "/":
			self.send_html(render_index_html())
			return

		if path == "/api/boundaries":
			self.send_json(load_boundary_geojson())
			return

		self.send_error(HTTPStatus.NOT_FOUND, "Not found")

	def do_POST(self) -> None:
		path = self.path.split("?", 1)[0]
		if path != "/api/parse":
			self.send_error(HTTPStatus.NOT_FOUND, "Not found")
			return

		content_length = int(self.headers.get("Content-Length", "0"))
		raw_body = self.rfile.read(content_length)

		try:
			payload = json.loads(raw_body.decode("utf-8"))
			message = str(payload.get("message", ""))
			parsed = parse_iridium_message(message)
		except ValueError as exc:
			self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
			return
		except json.JSONDecodeError:
			self.send_json({"error": "Request body was not valid JSON."}, status=HTTPStatus.BAD_REQUEST)
			return

		self.send_json(serialize_parsed_message(parsed))

	def log_message(self, format: str, *args: object) -> None:
		return

	def send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
		body = html.encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "text/html; charset=utf-8")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
		body = json.dumps(payload).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json; charset=utf-8")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)


def find_open_port() -> int:
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
		sock.bind(("127.0.0.1", 0))
		return int(sock.getsockname()[1])


def main() -> None:
	port = find_open_port()
	server = ThreadingHTTPServer(("127.0.0.1", port), IridiumRequestHandler)
	url = f"http://127.0.0.1:{port}"
	print(f"Serving Iridium Parser at {url}")
	webbrowser.open(url)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		pass
	finally:
		server.server_close()


if __name__ == "__main__":
	main()