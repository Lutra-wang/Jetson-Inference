import argparse
import copy
import json
import re
import subprocess
import threading
import time
from typing import Any, Dict, Optional, Tuple

from flask import Flask, Response, jsonify

from .config import apply_runtime_overrides, load_config
from .detector import create_detector
from .policy import TargetTrackingPolicy


INDEX_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Jetson Robot Vision Gateway</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111111;
      --surface: #1b1b1b;
      --surface-2: #242424;
      --border: #373737;
      --text: #f5f5f0;
      --muted: #aaa79f;
      --accent: #2fc18c;
      --warn: #e7b84b;
      --danger: #ef6f6c;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }
    main { width: min(1440px, 100%); margin: 0 auto; padding: 18px; }
    header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
    h1 { font-size: 22px; line-height: 1.15; font-weight: 700; margin: 0; letter-spacing: 0; }
    .sub { color: var(--muted); font-size: 13px; margin-top: 6px; }
    .status-pill { border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; background: var(--surface); min-width: 144px; text-align: center; }
    .status-pill strong { display: block; font-size: 20px; line-height: 1.15; }
    .status-pill span { display: block; color: var(--muted); font-size: 12px; margin-top: 4px; }
    .layout { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(320px, 0.8fr); gap: 16px; align-items: start; }
    .panel { border: 1px solid var(--border); border-radius: 8px; padding: 14px; background: var(--surface); }
    .video-panel { padding: 0; overflow: hidden; background: #050505; }
    .video-wrap { position: relative; width: 100%; aspect-ratio: 16 / 9; background: #050505; }
    .video-wrap img { display: block; width: 100%; height: 100%; object-fit: contain; }
    .metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .metric { border: 1px solid var(--border); border-radius: 8px; padding: 10px; background: var(--surface-2); min-height: 68px; }
    .metric span { color: var(--muted); font-size: 12px; display: block; }
    .metric strong { display: block; font-size: 19px; line-height: 1.2; margin-top: 7px; overflow-wrap: anywhere; }
    .section-title { font-size: 13px; color: var(--muted); margin: 0 0 10px; text-transform: uppercase; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; border-bottom: 1px solid var(--border); padding: 8px 4px; white-space: nowrap; }
    th { color: var(--muted); font-weight: 600; }
    td:last-child, th:last-child { text-align: right; }
    .stack { display: grid; gap: 12px; }
    .config-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; font-size: 13px; }
    .config-item { border: 1px solid var(--border); border-radius: 8px; padding: 8px; background: var(--surface-2); }
    .config-item span { color: var(--muted); display: block; font-size: 12px; }
    .config-item strong { display: block; margin-top: 4px; overflow-wrap: anywhere; }
    pre { margin: 0; max-height: 260px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.45; font-size: 12px; color: #ddd8ce; }
    .state-TRACKING { color: var(--accent); }
    .state-LOST { color: var(--warn); }
    .state-STOP, .state-ERROR { color: var(--danger); }
    @media (max-width: 900px) {
      main { padding: 12px; }
      header { align-items: stretch; flex-direction: column; }
      .layout { grid-template-columns: 1fr; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 520px) {
      .metrics, .config-grid { grid-template-columns: 1fr; }
      th:nth-child(3), td:nth-child(3) { display: none; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Jetson Robot Vision Gateway</h1>
        <div class="sub" id="runtime">connecting</div>
      </div>
      <div class="status-pill">
        <strong id="state">STARTING</strong>
        <span id="reason">waiting for first frame</span>
      </div>
    </header>
    <div class="layout">
      <section class="panel video-panel">
        <div class="video-wrap">
          <img src="/api/stream.mjpg" alt="live vision stream">
        </div>
      </section>
      <aside class="stack">
        <section class="panel">
          <div class="metrics">
            <div class="metric"><span>FPS</span><strong id="fps">-</strong></div>
            <div class="metric"><span>Frame</span><strong id="frame">-</strong></div>
            <div class="metric"><span>Linear X</span><strong id="linear">-</strong></div>
            <div class="metric"><span>Angular Z</span><strong id="angular">-</strong></div>
            <div class="metric"><span>Target</span><strong id="target">-</strong></div>
            <div class="metric"><span>Detections</span><strong id="det-count">-</strong></div>
            <div class="metric"><span>GPU</span><strong id="gpu">-</strong></div>
            <div class="metric"><span>RAM</span><strong id="ram">-</strong></div>
            <div class="metric"><span>Temp</span><strong id="temp">-</strong></div>
            <div class="metric"><span>Power</span><strong id="power">-</strong></div>
          </div>
        </section>
        <section class="panel">
          <h2 class="section-title">Detections</h2>
          <table>
            <thead><tr><th>Class</th><th>Conf</th><th>Area</th><th>Center</th></tr></thead>
            <tbody id="detections"><tr><td colspan="4">waiting</td></tr></tbody>
          </table>
        </section>
        <section class="panel">
          <h2 class="section-title">Runtime Config</h2>
          <div class="config-grid" id="config"></div>
        </section>
      </aside>
    </div>
    <section class="panel" style="margin-top:16px;">
      <h2 class="section-title">Status JSON</h2>
      <pre id="payload">waiting...</pre>
    </section>
  </main>
  <script>
    function fixed(value, digits = 3) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
      return Number(value).toFixed(digits);
    }

    function setText(id, text) {
      document.getElementById(id).textContent = text;
    }

    function renderDetections(detections) {
      const body = document.getElementById('detections');
      if (!detections || detections.length === 0) {
        body.innerHTML = '<tr><td colspan="4">no detections</td></tr>';
        return;
      }
      body.innerHTML = detections.map((item) => {
        const center = item.center ? `${Math.round(item.center[0])}, ${Math.round(item.center[1])}` : '-';
        return `<tr><td>${item.class_name}</td><td>${fixed(item.confidence, 2)}</td><td>${fixed(item.area_ratio, 3)}</td><td>${center}</td></tr>`;
      }).join('');
    }

    function renderConfig(runtime) {
      if (!runtime) return;
      const items = [
        ['backend', runtime.backend],
        ['camera', runtime.camera],
        ['network', runtime.network],
        ['threshold', runtime.threshold],
        ['target', runtime.target_class],
        ['deadband', runtime.center_deadband],
        ['max x', runtime.max_linear_x],
        ['max z', runtime.max_angular_z],
        ['stop area', runtime.stop_area_ratio],
        ['lost stop', runtime.lost_frames_to_stop],
        ['stream fps', runtime.stream_fps],
        ['jpeg quality', runtime.jpeg_quality],
        ['visualization', runtime.visualization_enabled ? 'on' : 'off'],
        ['tegrastats', runtime.tegrastats_enabled ? 'on' : 'off']
      ];
      document.getElementById('config').innerHTML = items.map(([label, value]) =>
        `<div class="config-item"><span>${label}</span><strong>${value}</strong></div>`
      ).join('');
    }

    async function tick() {
      try {
        const response = await fetch('/api/status', { cache: 'no-store' });
        const data = await response.json();
        const perception = data.perception || {};
        const policy = data.policy || {};
        const cmd = policy.cmd || {};
        const runtime = data.runtime || {};
        const perf = data.perf || {};
        const state = data.error ? 'ERROR' : (policy.state || 'STARTING');

        const stateEl = document.getElementById('state');
        stateEl.textContent = state;
        stateEl.className = `state-${state}`;

        setText('reason', data.error || policy.reason || '-');
        setText('runtime', `${runtime.backend || '-'} | ${runtime.camera || '-'} | ${runtime.network || '-'}`);
        setText('fps', fixed(perception.fps, 1));
        setText('frame', perception.frame_id ?? '-');
        setText('linear', fixed(cmd.linear_x));
        setText('angular', fixed(cmd.angular_z));
        setText('target', policy.target || '-');
        setText('det-count', (perception.detections || []).length);
        setText('gpu', perf.gr3d ? `${perf.gr3d.util_pct ?? '-'}% @ ${perf.gr3d.freq_mhz ?? '-'}MHz` : '-');
        setText('ram', perf.ram ? `${perf.ram.used_mb}/${perf.ram.total_mb}MB` : '-');
        setText('temp', perf.temps && perf.temps.CPU !== undefined ? `${fixed(perf.temps.CPU, 1)}C` : '-');
        setText('power', perf.power && perf.power.VDD_IN ? `${perf.power.VDD_IN.instant_mw}mW` : '-');
        renderDetections(perception.detections || []);
        renderConfig(runtime);
        document.getElementById('payload').textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        setText('reason', String(err));
      }
    }
    setInterval(tick, 500);
    tick();
  </script>
</body>
</html>
"""


def _runtime_snapshot(
    config: Dict[str, Any],
    selected_backend: str,
    stream_fps: float,
    jpeg_quality: int,
    visualization_enabled: bool,
    tegrastats_enabled: bool,
) -> Dict[str, Any]:
    camera_cfg = config.get("camera", {})
    detector_cfg = config.get("detector", {})
    policy_cfg = config.get("policy", {})
    return {
        "backend": selected_backend,
        "camera": "{uri} {width}x{height}@{fps} {codec}".format(
            uri=camera_cfg.get("uri", "-"),
            width=camera_cfg.get("width", "-"),
            height=camera_cfg.get("height", "-"),
            fps=camera_cfg.get("fps", "-"),
            codec=camera_cfg.get("codec", ""),
        ),
        "network": detector_cfg.get("network", "-"),
        "threshold": detector_cfg.get("threshold", "-"),
        "target_class": policy_cfg.get("target_class", detector_cfg.get("target_class", "-")),
        "center_deadband": policy_cfg.get("center_deadband", "-"),
        "max_linear_x": policy_cfg.get("max_linear_x", "-"),
        "max_angular_z": policy_cfg.get("max_angular_z", "-"),
        "stop_area_ratio": policy_cfg.get("stop_area_ratio", "-"),
        "lost_frames_to_stop": policy_cfg.get("lost_frames_to_stop", "-"),
        "stream_fps": stream_fps,
        "jpeg_quality": jpeg_quality,
        "visualization_enabled": visualization_enabled,
        "tegrastats_enabled": tegrastats_enabled,
        "stream": "/api/stream.mjpg",
        "perf": "/api/perf",
    }


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_tegrastats_line(line: str) -> Dict[str, Any]:
    """Parse the common tegrastats fields used by the dashboard."""
    payload: Dict[str, Any] = {
        "enabled": True,
        "raw": line.strip(),
        "ts": time.time(),
    }

    match = re.search(r"\bRAM\s+(\d+)/(\d+)MB\b", line)
    if match:
        payload["ram"] = {
            "used_mb": int(match.group(1)),
            "total_mb": int(match.group(2)),
        }

    match = re.search(r"\bSWAP\s+(\d+)/(\d+)MB\b", line)
    if match:
        payload["swap"] = {
            "used_mb": int(match.group(1)),
            "total_mb": int(match.group(2)),
        }

    match = re.search(r"\bGR3D_FREQ\s+(\d+)%@?(\d+)?\b", line)
    if match:
        payload["gr3d"] = {
            "util_pct": int(match.group(1)),
            "freq_mhz": _parse_int(match.group(2)),
        }

    match = re.search(r"\bEMC_FREQ\s+(\d+)%@?(\d+)?\b", line)
    if match:
        payload["emc"] = {
            "util_pct": int(match.group(1)),
            "freq_mhz": _parse_int(match.group(2)),
        }

    match = re.search(r"\bCPU\s+\[([^\]]+)\]", line)
    if match:
        payload["cpu"] = {"raw": match.group(1)}

    temps: Dict[str, float] = {}
    for name, value in re.findall(r"\b([A-Za-z0-9_]+)@([0-9.]+)C\b", line):
        try:
            temps[name] = float(value)
        except ValueError:
            continue
    if temps:
        payload["temps"] = temps

    power: Dict[str, Dict[str, int]] = {}
    for name, instant, average in re.findall(r"\b([A-Z0-9_]+)\s+(\d+)/(\d+)\b", line):
        if not (name.startswith("VDD") or name.startswith("POM")):
            continue
        power[name] = {
            "instant_mw": int(instant),
            "average_mw": int(average),
        }
    if power:
        payload["power"] = power

    return payload


class TegrastatsMonitor:
    def __init__(self, interval_ms: int = 1000) -> None:
        self.interval_ms = max(int(interval_ms), 100)
        self._lock = threading.Lock()
        self._latest: Dict[str, Any] = {
            "enabled": True,
            "error": "waiting for tegrastats",
        }
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._latest)

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._latest = {
                "enabled": True,
                "error": message,
                "ts": time.time(),
            }

    def _run(self) -> None:
        try:
            self._process = subprocess.Popen(
                ["tegrastats", "--interval", str(self.interval_ms)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )
        except OSError as exc:
            self._set_error(str(exc))
            return

        if self._process.stdout is None:
            self._set_error("tegrastats stdout unavailable")
            return

        for line in self._process.stdout:
            with self._lock:
                self._latest = parse_tegrastats_line(line)

        return_code = self._process.poll()
        self._set_error("tegrastats exited with code {0}".format(return_code))


def _load_visual_deps() -> Tuple[Any, Any]:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    return cv2, np


def _frame_dimensions(perception: Dict[str, Any], config: Dict[str, Any]) -> Tuple[int, int]:
    camera_cfg = config.get("camera", {})
    width = int(perception.get("width") or camera_cfg.get("width", 640))
    height = int(perception.get("height") or camera_cfg.get("height", 480))
    return max(width, 1), max(height, 1)


def _blank_frame(width: int, height: int, cv2: Any, np: Any) -> Any:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = (18, 18, 18)
    step = max(min(width, height) // 8, 48)
    for x in range(0, width, step):
        cv2.line(frame, (x, 0), (x, height), (38, 38, 38), 1)
    for y in range(0, height, step):
        cv2.line(frame, (0, y), (width, y), (38, 38, 38), 1)
    cv2.putText(frame, "mock camera", (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (190, 190, 190), 2)
    return frame


def _normalize_frame(source_frame: Optional[Any], width: int, height: int, cv2: Any, np: Any) -> Any:
    if source_frame is None:
        return _blank_frame(width, height, cv2, np)

    array = np.asarray(source_frame)
    if array.size == 0:
        return _blank_frame(width, height, cv2, np)

    frame = np.array(array, copy=True)
    if frame.dtype != np.uint8:
        frame = frame.astype(np.float32)
        max_value = float(frame.max()) if frame.size else 0.0
        if max_value <= 1.0:
            frame *= 255.0
        frame = np.clip(frame, 0, 255).astype(np.uint8)

    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    elif frame.ndim == 3 and frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
    elif frame.ndim == 3 and frame.shape[2] == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    elif frame.ndim == 3 and frame.shape[2] == 1:
        frame = cv2.cvtColor(frame[:, :, 0], cv2.COLOR_GRAY2BGR)
    else:
        frame = _blank_frame(width, height, cv2, np)

    return np.ascontiguousarray(frame)


def _state_color(state: str) -> Tuple[int, int, int]:
    if state == "TRACKING":
        return 140, 193, 47
    if state == "LOST":
        return 75, 184, 231
    return 108, 111, 239


def _draw_header(frame: Any, perception: Dict[str, Any], policy: Dict[str, Any], error: Optional[str], cv2: Any) -> None:
    height, width = frame.shape[:2]
    state = "ERROR" if error else str(policy.get("state", "STARTING"))
    cmd = policy.get("cmd", {}) or {}
    fps = float(perception.get("fps") or 0.0)
    detections = perception.get("detections", []) or []
    label = "{state} | fps={fps:.1f} | detections={count} | x={linear:.3f} z={angular:.3f}".format(
        state=state,
        fps=fps,
        count=len(detections),
        linear=float(cmd.get("linear_x") or 0.0),
        angular=float(cmd.get("angular_z") or 0.0),
    )
    cv2.rectangle(frame, (0, 0), (width, 42), (16, 16, 16), -1)
    cv2.rectangle(frame, (0, 0), (8, 42), _state_color(state), -1)
    cv2.putText(frame, label, (18, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (245, 245, 240), 2)
    if error:
        cv2.putText(frame, error[:80], (18, min(height - 18, 66)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (108, 111, 239), 2)


def _draw_detections(frame: Any, perception: Dict[str, Any], policy: Dict[str, Any], cv2: Any) -> None:
    frame_h, frame_w = frame.shape[:2]
    src_w = float(perception.get("width") or frame_w)
    src_h = float(perception.get("height") or frame_h)
    scale_x = frame_w / max(src_w, 1.0)
    scale_y = frame_h / max(src_h, 1.0)
    state = str(policy.get("state", ""))
    target = policy.get("target")

    for item in perception.get("detections", []) or []:
        bbox = item.get("bbox", [0, 0, 0, 0])
        left = max(0, min(frame_w - 1, int(float(bbox[0]) * scale_x)))
        top = max(0, min(frame_h - 1, int(float(bbox[1]) * scale_y)))
        right = max(0, min(frame_w - 1, int(float(bbox[2]) * scale_x)))
        bottom = max(0, min(frame_h - 1, int(float(bbox[3]) * scale_y)))
        is_target = item.get("class_name") == target and state == "TRACKING"
        color = (140, 193, 47) if is_target else (75, 184, 231)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

        center = item.get("center", None)
        if center:
            cx = max(0, min(frame_w - 1, int(float(center[0]) * scale_x)))
            cy = max(0, min(frame_h - 1, int(float(center[1]) * scale_y)))
            cv2.circle(frame, (cx, cy), 4, color, -1)

        label = "{name} {confidence:.2f}".format(
            name=item.get("class_name", "-"),
            confidence=float(item.get("confidence") or 0.0),
        )
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.56, 2)
        label_y = max(top, text_h + 10)
        cv2.rectangle(frame, (left, label_y - text_h - 8), (min(frame_w - 1, left + text_w + 10), label_y + baseline), color, -1)
        cv2.putText(frame, label, (left + 5, label_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (10, 10, 10), 2)


def _encode_visual_frame(
    source_frame: Optional[Any],
    perception: Dict[str, Any],
    policy: Dict[str, Any],
    config: Dict[str, Any],
    error: Optional[str],
    jpeg_quality: int,
) -> bytes:
    cv2, np = _load_visual_deps()
    width, height = _frame_dimensions(perception, config)
    frame = _normalize_frame(source_frame, width, height, cv2, np)
    _draw_detections(frame, perception, policy, cv2)
    _draw_header(frame, perception, policy, error, cv2)
    quality = max(30, min(int(jpeg_quality), 95))
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("failed to encode MJPEG frame")
    return encoded.tobytes()


def create_app(
    config: Dict[str, Any],
    backend: Optional[str] = None,
    stream_fps: Optional[float] = None,
    jpeg_quality: Optional[int] = None,
    visualization_enabled: Optional[bool] = None,
    tegrastats_enabled: Optional[bool] = None,
    tegrastats_interval_ms: Optional[int] = None,
) -> Flask:
    app = Flask(__name__)
    selected_backend = backend or str(config["detector"].get("backend", "mock"))
    web_cfg = config.get("web", {})
    selected_stream_fps = float(stream_fps if stream_fps is not None else web_cfg.get("stream_fps", 10.0))
    selected_stream_fps = max(selected_stream_fps, 0.1)
    selected_jpeg_quality = int(jpeg_quality if jpeg_quality is not None else web_cfg.get("jpeg_quality", 75))
    selected_jpeg_quality = max(30, min(selected_jpeg_quality, 95))
    selected_visualization = bool(
        visualization_enabled if visualization_enabled is not None else web_cfg.get("visualization_enabled", True)
    )
    selected_tegrastats = bool(
        tegrastats_enabled if tegrastats_enabled is not None else web_cfg.get("tegrastats_enabled", False)
    )
    selected_tegrastats_interval_ms = int(
        tegrastats_interval_ms if tegrastats_interval_ms is not None else web_cfg.get("tegrastats_interval_ms", 1000)
    )

    try:
        _load_visual_deps()
    except ImportError:
        pass
    detector = create_detector(config, selected_backend)
    detector.set_visualization_enabled(selected_visualization)
    policy = TargetTrackingPolicy(config)
    loop_delay = 0.1 if selected_backend == "mock" else 0.0
    stream_period = 1.0 / selected_stream_fps
    perf_monitor = TegrastatsMonitor(selected_tegrastats_interval_ms) if selected_tegrastats else None
    if perf_monitor is not None:
        perf_monitor.start()
    state_lock = threading.Lock()

    state: Dict[str, Any] = {
        "perception": {},
        "policy": {"state": "STARTING", "cmd": {"linear_x": 0.0, "angular_z": 0.0}},
        "runtime": _runtime_snapshot(
            config,
            selected_backend,
            selected_stream_fps,
            selected_jpeg_quality,
            selected_visualization,
            selected_tegrastats,
        ),
        "error": None,
    }

    def _perf_payload() -> Dict[str, Any]:
        if perf_monitor is None:
            return {"enabled": False}
        return perf_monitor.snapshot()

    def _status_payload() -> Dict[str, Any]:
        with state_lock:
            payload = copy.deepcopy(state)
        payload["perf"] = _perf_payload()
        return payload

    def worker() -> None:
        frame_id = 0
        while True:
            try:
                perception = detector.detect(frame=None, frame_id=frame_id)
                decision = policy.update(perception)
                with state_lock:
                    state["perception"] = perception.to_dict()
                    state["policy"] = decision.to_dict()
                    state["error"] = None
                frame_id += 1
            except Exception as exc:
                with state_lock:
                    state["error"] = str(exc)
                time.sleep(0.5)
            if loop_delay > 0.0:
                time.sleep(loop_delay)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    @app.route("/", methods=["GET"])
    def index() -> Response:
        return Response(INDEX_HTML, mimetype="text/html")

    @app.route("/api/status", methods=["GET"])
    def status() -> Response:
        return jsonify(_status_payload())

    @app.route("/api/status.ndjson", methods=["GET"])
    def status_stream() -> Response:
        def generate():
            while True:
                payload = _status_payload()
                yield json.dumps(payload, ensure_ascii=False) + "\n"
                time.sleep(0.5)

        return Response(generate(), mimetype="application/x-ndjson")

    @app.route("/api/perf", methods=["GET"])
    def perf() -> Response:
        return jsonify(_perf_payload())

    @app.route("/api/stream.mjpg", methods=["GET"])
    def video_stream() -> Response:
        if not selected_visualization:
            return Response(
                "video stream is disabled by --disable-visualization\n",
                status=503,
                mimetype="text/plain",
            )

        try:
            _load_visual_deps()
        except ImportError as exc:
            return Response(
                "video stream requires OpenCV. Install python3-opencv on Jetson or opencv-python locally.\n{0}\n".format(exc),
                status=503,
                mimetype="text/plain",
            )

        def generate():
            while True:
                with state_lock:
                    perception = copy.deepcopy(state.get("perception", {}))
                    policy_state = copy.deepcopy(state.get("policy", {}))
                    error = state.get("error")
                frame = _encode_visual_frame(
                    detector.latest_frame(),
                    perception,
                    policy_state,
                    config,
                    error,
                    selected_jpeg_quality,
                )
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n"
                    b"Content-Length: " + str(len(frame)).encode("ascii") + b"\r\n\r\n" + frame + b"\r\n"
                )
                time.sleep(stream_period)

        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run web dashboard")
    parser.add_argument("--config", default=None)
    parser.add_argument("--backend", choices=["mock", "jetson"], default=None)
    parser.add_argument("--camera", default=None)
    parser.add_argument("--network", default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=int, default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--stream-fps", type=float, default=None)
    parser.add_argument("--jpeg-quality", type=int, default=None)
    parser.add_argument("--disable-visualization", action="store_true")
    parser.add_argument("--enable-tegrastats", action="store_true")
    parser.add_argument("--tegrastats-interval-ms", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    apply_runtime_overrides(
        config,
        backend=args.backend,
        camera=args.camera,
        network=args.network,
        threshold=args.threshold,
        width=args.width,
        height=args.height,
        fps=args.fps,
    )
    app = create_app(
        config,
        stream_fps=args.stream_fps,
        jpeg_quality=args.jpeg_quality,
        visualization_enabled=False if args.disable_visualization else None,
        tegrastats_enabled=True if args.enable_tegrastats else None,
        tegrastats_interval_ms=args.tegrastats_interval_ms,
    )
    web_cfg = config["web"]
    app.run(
        host=args.host or str(web_cfg.get("host", "0.0.0.0")),
        port=args.port or int(web_cfg.get("port", 5000)),
        threaded=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
