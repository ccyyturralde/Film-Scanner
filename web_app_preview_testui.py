
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Film Scanner Test App (Preview Stream + Rich UI)
------------------------------------------------
This is a standalone test UI for Canon R100 live preview and capture. It does NOT
replace your main app; it's meant to evaluate the continuous MJPEG preview path.

Features
- Continuous live preview via MJPEG (/preview.mjpg) with a background worker
- Start/Stop Preview, Capture, Viewfinder toggle
- Adjustable FPS for preview (4–15) without restarting
- Generic get/set config endpoints for gphoto2
- Status badges and a simple rolling server log viewer
- Keyboard shortcuts: Space = Capture, P = Start/Stop preview, V = Toggle VF
- Rotation control (client-side CSS transform), auto-retry stream

Notes
- Preview worker respects camera_op_lock, so capture is never interrupted.
- Status checks do not kill gphoto2.
- Capture writes to card (capturetarget=1). Adjust later as desired.
"""

import os
import re
import sys
import time
import json
import math
import shutil
import queue
import threading
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, Response, make_response

app = Flask(__name__)

# ---------------------------- HTML / Frontend ----------------------------

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Film Scanner Test UI</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin:0; background:#0b0b0b; color:#eaeaea; }
  header { padding: 16px 20px; border-bottom: 1px solid #222; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
  h2 { margin:0; font-size:20px; }
  .badge { padding:4px 10px; border-radius:999px; background:#1c1c1c; border:1px solid #2a2a2a; font-size:12px; }
  .ok { background:#15361f; border-color:#214e2a; }
  .warn { background:#3a1f1b; border-color:#5a2e28; }
  .grid { display:grid; gap:16px; grid-template-columns: 1fr; max-width:1100px; margin: 20px auto; padding: 0 16px; }
  .card { background:#0f0f0f; border:1px solid #222; border-radius:12px; }
  .card h3 { margin:0; padding:14px 16px; font-size:14px; border-bottom:1px solid #1d1d1d; color:#cfcfcf; }
  .card .body { padding:14px 16px; }
  .row { display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
  .grow { flex:1; }
  button, select, input[type=number], input[type=range] {
    background:#1b1e27; color:#fff; border:1px solid #2a2f3a; border-radius:10px; padding:8px 12px; font-weight:600;
  }
  button { cursor:pointer; }
  button.secondary { background: #222; border-color:#333; font-weight:500; }
  button:disabled { opacity:0.5; cursor:not-allowed; }
  img.preview { width:100%; max-height:72vh; object-fit:contain; background:#111; border-radius:10px; }
  .muted { color:#a8a8a8; font-size:12px; }
  details { background:#0f0f0f; border-radius:10px; }
  pre { max-height:200px; overflow:auto; white-space:pre-wrap; background:#0b0b0b; border:1px solid #1f1f1f; padding:8px; border-radius:8px; }
  .hint { font-size:12px; color:#aaa; }
  .spacer { flex:1; }
</style>
</head>
<body>
  <header>
    <h2>Film Scanner — Test UI</h2>
    <span id="cam" class="badge">Camera: …</span>
    <span id="vf"  class="badge">Viewfinder: …</span>
    <span id="pv"  class="badge">Preview: …</span>
    <span id="ts"  class="badge">—</span>
    <span class="spacer"></span>
    <span class="hint">Shortcuts: <b>Space</b>=Capture, <b>P</b>=Preview on/off, <b>V</b>=VF on/off</span>
  </header>

  <div class="grid">
    <div class="card">
      <h3>Live Preview</h3>
      <div class="body">
        <div class="row" style="gap:8px; margin-bottom:10px">
          <button id="btnStart">Start Preview</button>
          <button id="btnStop" class="secondary">Stop Preview</button>
          <button id="btnShot">Capture</button>
          <label class="row" style="gap:6px">FPS
            <input id="fps" type="range" min="4" max="15" value="8" />
            <span id="fpsVal" class="muted">8</span>
          </label>
          <label class="row" style="gap:6px">Rotate
            <select id="rotate">
              <option value="0">0°</option>
              <option value="90">90°</option>
              <option value="180">180°</option>
              <option value="270">270°</option>
            </select>
          </label>
          <button id="btnVF" class="secondary">Toggle Viewfinder</button>
          <span id="msg" class="muted"></span>
        </div>
        <img id="live" class="preview" alt="Live preview stream" />
      </div>
    </div>

    <div class="card">
      <h3>Camera Config (basic)</h3>
      <div class="body row">
        <input id="cfgName" class="grow" placeholder="e.g. shutterspeed / iso / aperture / capturetarget" />
        <input id="cfgVal"  class="grow" placeholder="e.g. 1/60 / 400 / 5.6 / 1" />
        <button id="btnCfgGet" class="secondary">Get</button>
        <button id="btnCfgSet">Set</button>
      </div>
      <div class="body">
        <pre id="cfgOut" class="muted">Result will appear here…</pre>
      </div>
    </div>

    <div class="card">
      <h3>Logs</h3>
      <div class="body">
        <pre id="log" class="muted">Waiting…</pre>
      </div>
    </div>
  </div>

<script>
const $ = sel => document.querySelector(sel);
const msg = t => { $("#msg").textContent = t || ""; };

let previewOn = false;
let currentRotation = 0;

function applyRotation() {
  const deg = parseInt($("#rotate").value || "0", 10) || 0;
  $("#live").style.transform = "rotate(" + deg + "deg)";
}

async function statusTick(){
  try{
    const r = await fetch('/api/status');
    const j = await r.json();
    $("#cam").textContent = "Camera: " + (j.camera_connected ? (j.camera_name || "Connected") : "Not found");
    $("#cam").className = "badge " + (j.camera_connected ? "ok" : "warn");
    $("#vf").textContent = "Viewfinder: " + (j.viewfinder ? "On" : "Off");
    $("#pv").textContent = "Preview: " + (j.preview_running ? "Running" : "Stopped");
    $("#ts").textContent = j.time || "";
  }catch(e){ /* ignore */ }
}

async function refreshLogs(){
  try{
    const r = await fetch('/api/logs');
    const j = await r.json();
    $("#log").textContent = (j.lines || []).join("\\n") || "No logs yet.";
  }catch(e){
    /* ignore */
  }
}

async function startPreview(){
  msg("Starting preview…");
  await fetch('/api/preview/start', {method:'POST'});
  previewOn = true;
  const cacheBust = Date.now();
  $("#live").src = "/preview.mjpg?ts=" + cacheBust;
  msg("");
}

async function stopPreview(){
  msg("Stopping preview…");
  $("#live").src = "";
  previewOn = false;
  await fetch('/api/preview/stop', {method:'POST'});
  msg("");
}

async function capture(){
  msg("Capturing…");
  try{
    const r = await fetch('/api/test_capture', {method:'POST'});
    const j = await r.json();
    msg(j.ok ? "Capture OK" : "Capture failed");
  }catch(e){
    msg("Capture error");
  }
  setTimeout(()=>msg(""), 1200);
}

async function toggleVF(){
  msg("Toggling viewfinder…");
  try{
    const r = await fetch('/api/viewfinder', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({toggle:true})});
    const j = await r.json();
    msg(j.viewfinder ? "VF On" : "VF Off");
  }catch(e){ msg("VF toggle error"); }
  setTimeout(()=>msg(""), 900);
}

async function setFPS(v){
  $("#fpsVal").textContent = v;
  await fetch('/api/preview/fps', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({fps: parseInt(v,10)})});
}

async function cfgGet(){
  const name = $("#cfgName").value.trim();
  if(!name){ $("#cfgOut").textContent = "Enter a config name."; return; }
  $("#cfgOut").textContent = "Reading…";
  const r = await fetch('/api/config/get?name=' + encodeURIComponent(name));
  const j = await r.json();
  $("#cfgOut").textContent = j.ok ? j.output : (j.error || "Error");
}

async function cfgSet(){
  const name = $("#cfgName").value.trim();
  const value = $("#cfgVal").value.trim();
  if(!name || !value){ $("#cfgOut").textContent = "Enter name and value."; return; }
  $("#cfgOut").textContent = "Setting…";
  const r = await fetch('/api/config/set', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name, value})});
  const j = await r.json();
  $("#cfgOut").textContent = j.ok ? (j.output || "OK") : (j.error || "Error");
}

$("#btnStart").addEventListener("click", startPreview);
$("#btnStop").addEventListener("click", stopPreview);
$("#btnShot").addEventListener("click", capture);
$("#btnVF").addEventListener("click", toggleVF);
$("#rotate").addEventListener("change", applyRotation);
$("#fps").addEventListener("input", (e)=> setFPS(e.target.value));
$("#btnCfgGet").addEventListener("click", cfgGet);
$("#btnCfgSet").addEventListener("click", cfgSet);

// Auto start
startPreview().catch(()=>{});
applyRotation();
setInterval(statusTick, 1000);
setInterval(refreshLogs, 1200);

// Reconnect MJPEG on error (simple strategy)
$("#live").addEventListener("error", ()=>{
  if(!previewOn) return;
  setTimeout(()=>{ $("#live").src = "/preview.mjpg?ts=" + Date.now(); }, 500);
});

// Keyboard shortcuts
window.addEventListener("keydown", (e)=>{
  if (e.code === "Space"){ e.preventDefault(); capture(); }
  if (e.key === "p" || e.key === "P"){ previewOn ? stopPreview() : startPreview(); }
  if (e.key === "v" || e.key === "V"){ toggleVF(); }
});
</script>
</body>
</html>
"""

# ---------------------------- Backend ----------------------------

class RingLog:
    """Simple ring buffer for log messages exposed at /api/logs."""
    def __init__(self, capacity=200):
        self.capacity = capacity
        self.buf = []
        self.lock = threading.Lock()

    def add(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.buf.append(f"[{ts}] {line}")
            if len(self.buf) > self.capacity:
                self.buf = self.buf[-self.capacity:]

    def lines(self):
        with self.lock:
            return list(self.buf)

ringlog = RingLog()

class FilmScanner:
    def __init__(self):
        self.camera_connected = False
        self.camera_name = ""
        self.viewfinder_enabled = False

        self.lock = threading.Lock()
        self.camera_op_lock = threading.Lock()

        self.preview_enabled = False
        self._preview_thread = None
        self._preview_stop = threading.Event()
        self._last_frame = None
        self._preview_fps = 8

        self.last_capture_failed = False

        try:
            self.check_camera()
        except Exception as e:
            ringlog.add(f"Initial camera check error: {e}")

    # ---------- utilities ----------
    def _kill_gphoto2(self):
        try:
            subprocess.run(["killall", "gphoto2"], capture_output=True, text=True, timeout=1)
            ringlog.add("killall gphoto2")
        except Exception:
            pass
        time.sleep(0.15)

    # ---------- camera checks (read-only) ----------
    def check_camera(self):
        try:
            if self.camera_op_lock.locked():
                return self.camera_connected
            result = subprocess.run(["gphoto2", "--auto-detect"], capture_output=True, timeout=5, text=True)
            if result.returncode == 0 and "usb" in result.stdout.lower():
                for line in result.stdout.splitlines():
                    if "usb:" in line.lower():
                        self.camera_connected = True
                        self.camera_name = line.strip()
                        ringlog.add(f"Camera: {self.camera_name}")
                        break
            else:
                self.camera_connected = False
        except Exception as e:
            ringlog.add(f"check_camera error: {e}")
        return self.camera_connected

    def check_viewfinder_state(self):
        try:
            if self.camera_op_lock.locked():
                return self.viewfinder_enabled
            result = subprocess.run(["gphoto2", "--get-config", "viewfinder"], capture_output=True, timeout=4, text=True)
            if result.returncode == 0 and result.stdout:
                out = result.stdout
                if "Current: 1" in out or "Current: On" in out:
                    self.viewfinder_enabled = True
                elif "Current: 0" in out or "Current: Off" in out:
                    self.viewfinder_enabled = False
        except Exception as e:
            ringlog.add(f"check_viewfinder_state error: {e}")
        return self.viewfinder_enabled

    # ---------- capture ----------
    def capture_image(self, retry=True):
        try:
            self.camera_op_lock.acquire()
            if self.last_capture_failed:
                self._kill_gphoto2()

            # prefer writing to card for speed
            subprocess.run(["gphoto2", "--set-config", "capturetarget=1"],
                           capture_output=True, text=True, timeout=3)

            ringlog.add("Capture: start")
            result = subprocess.run(["gphoto2", "--capture-image"],
                                    capture_output=True, timeout=10, text=True)
            ringlog.add(f"Capture rc={result.returncode}")
            if result.stdout: ringlog.add("stdout: " + result.stdout.strip())
            if result.stderr: ringlog.add("stderr: " + result.stderr.strip())

            success = (result.returncode == 0)
            if not success and result.stderr:
                low = result.stderr.lower()
                if any(k in low for k in ["ptp i/o error", "device busy", "resource busy", "usb device reset", "i/o in progress"]):
                    success = True

            self.last_capture_failed = not success
            if success:
                ringlog.add("Capture OK")
                return True

            if retry:
                ringlog.add("Capture retry (reset gphoto2)")
                self._kill_gphoto2()
                return self.capture_image(retry=False)

            ringlog.add("Capture failed")
            return False

        except Exception as e:
            ringlog.add(f"capture_image error: {e}")
            self.last_capture_failed = True
            return False
        finally:
            if self.camera_op_lock.locked():
                try: self.camera_op_lock.release()
                except RuntimeError: pass

    # ---------- preview worker ----------
    def _preview_loop(self):
        self.preview_enabled = True
        try:
            subprocess.run(["gphoto2", "--set-config", "viewfinder=1"],
                           capture_output=True, text=True, timeout=3)
        except Exception as e:
            ringlog.add(f"enable viewfinder error: {e}")

        ringlog.add("Preview loop started")
        while not self._preview_stop.is_set():
            # dynamic FPS
            interval = 1.0 / max(1, int(self._preview_fps))

            if self.camera_op_lock.locked():
                time.sleep(0.02)
                continue

            t0 = time.time()
            try:
                proc = subprocess.run(["gphoto2", "--capture-preview", "--stdout"],
                                      capture_output=True, timeout=2)
                if proc.returncode == 0 and proc.stdout:
                    self._last_frame = proc.stdout
                else:
                    if proc.stderr:
                        try:
                            msg = proc.stderr.decode("utf-8", errors="ignore")
                        except Exception:
                            msg = str(proc.stderr)
                        msg = (msg or "").strip()
                        if msg:
                            ringlog.add("preview stderr: " + msg)
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                ringlog.add(f"preview loop error: {e}")

            elapsed = time.time() - t0
            sleep_for = max(0, interval - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

        try:
            subprocess.run(["gphoto2", "--set-config", "viewfinder=0"],
                           capture_output=True, text=True, timeout=3)
        except Exception as e:
            ringlog.add(f"disable viewfinder error: {e}")
        self.preview_enabled = False
        ringlog.add("Preview loop stopped")

    def start_preview(self):
        if self._preview_thread and self._preview_thread.is_alive():
            return True
        self._preview_stop.clear()
        self._preview_thread = threading.Thread(target=self._preview_loop, daemon=True)
        self._preview_thread.start()
        return True

    def stop_preview(self):
        self._preview_stop.set()
        if self._preview_thread:
            self._preview_thread.join(timeout=2)
        self._preview_thread = None
        return True

    def status(self):
        return {
            "camera_connected": bool(self.camera_connected),
            "camera_name": self.camera_name,
            "viewfinder": bool(self.viewfinder_enabled),
            "preview_running": bool(self.preview_enabled),
            "last_capture_failed": bool(self.last_capture_failed),
            "time": datetime.now().isoformat(timespec="seconds"),
            "fps": int(self._preview_fps),
        }

scanner = FilmScanner()

# ---------------------------- Routes ----------------------------

@app.route("/")
def index_page():
    resp = make_response(INDEX_HTML)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp

@app.route("/api/status")
def api_status():
    scanner.check_camera()
    scanner.check_viewfinder_state()
    return jsonify(scanner.status())

@app.route("/api/test_capture", methods=["POST"])
def api_test_capture():
    ok = scanner.capture_image(retry=True)
    return jsonify({"ok": bool(ok)})

@app.route("/api/preview/start", methods=["POST"])
def api_preview_start():
    ok = scanner.start_preview()
    return jsonify({"ok": bool(ok)})

@app.route("/api/preview/stop", methods=["POST"])
def api_preview_stop():
    ok = scanner.stop_preview()
    return jsonify({"ok": bool(ok)})

@app.route("/api/preview/fps", methods=["POST"])
def api_preview_fps():
    data = request.get_json(force=True, silent=True) or {}
    fps = int(data.get("fps", 8))
    fps = max(1, min(20, fps))
    scanner._preview_fps = fps
    ringlog.add(f"Set preview FPS: {fps}")
    return jsonify({"ok": True, "fps": fps})

@app.route("/api/viewfinder", methods=["POST"])
def api_viewfinder():
    data = request.get_json(force=True, silent=True) or {}
    enabled = data.get("enabled")
    toggle = data.get("toggle")
    if toggle:
        # Read current state and flip
        now = scanner.check_viewfinder_state()
        enabled = not now
    if enabled is None:
        return jsonify({"ok": False, "error": "Missing 'enabled' or 'toggle'"}), 400
    # Avoid touching while capture in progress
    if scanner.camera_op_lock.locked():
        return jsonify({"ok": False, "error": "busy"}), 409
    try:
        val = "1" if enabled else "0"
        subprocess.run(["gphoto2", "--set-config", f"viewfinder={val}"],
                       capture_output=True, text=True, timeout=3)
        scanner.viewfinder_enabled = bool(enabled)
        ringlog.add(f"Viewfinder set to {enabled}")
        return jsonify({"ok": True, "viewfinder": scanner.viewfinder_enabled})
    except Exception as e:
        ringlog.add(f"viewfinder set error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/config/get")
def api_config_get():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Missing config name"}), 400
    try:
        r = subprocess.run(["gphoto2", "--get-config", name], capture_output=True, text=True, timeout=5)
        out = r.stdout or r.stderr or ""
        ringlog.add(f"get-config {name} rc={r.returncode}")
        return jsonify({"ok": True, "output": out.strip(), "rc": r.returncode})
    except Exception as e:
        ringlog.add(f"get-config error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/config/set", methods=["POST"])
def api_config_set():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    value = (data.get("value") or "").strip()
    if not name or not value:
        return jsonify({"ok": False, "error": "Missing name/value"}), 400
    if scanner.camera_op_lock.locked():
        return jsonify({"ok": False, "error": "busy"}), 409
    try:
        r = subprocess.run(["gphoto2", "--set-config", f"{name}={value}"], capture_output=True, text=True, timeout=5)
        out = r.stdout or r.stderr or ""
        ringlog.add(f"set-config {name}={value} rc={r.returncode}")
        return jsonify({"ok": r.returncode == 0, "output": out.strip(), "rc": r.returncode})
    except Exception as e:
        ringlog.add(f"set-config error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/logs")
def api_logs():
    return jsonify({"lines": ringlog.lines()})

@app.route("/preview.mjpg")
def preview_mjpg():
    boundary = "frame"
    def gen():
        scanner.start_preview()
        while True:
            frame = scanner._last_frame
            if frame:
                yield (b"--" + boundary.encode() + b"\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" +
                       frame + b"\r\n")
            else:
                time.sleep(0.03)
    return Response(gen(), mimetype=f"multipart/x-mixed-replace; boundary=%s" % boundary)

# ---------------------------- Entrypoint ----------------------------

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = bool(int(os.environ.get("DEBUG", "0")))
    print(f"Starting Film Scanner Test app on {host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)
"""
"""
