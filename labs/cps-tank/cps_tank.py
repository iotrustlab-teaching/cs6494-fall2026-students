#!/usr/bin/env python3
"""A two-process CPS tank demo using only the Python standard library.

The process owns the physical truth. The controller sees only the sensor value
sent over the network. In the spoof scenario those two values diverge.
"""

from __future__ import annotations

import argparse
import json
import secrets
import socket
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse


# macOS commonly reserves 5000 for AirPlay Receiver, so use a quiet high port.
DEFAULT_PORT = 55049
LOW_LEVEL = 45.0
HIGH_LEVEL = 55.0
HIGH_HIGH_LEVEL = 90.0
OVERFLOW_LEVEL = 100.0


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CS 6494 CPS Evidence Lab</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #091016;
      --panel: #111d26;
      --panel-2: #172732;
      --line: #2d4350;
      --text: #eef6f8;
      --muted: #9fb3bd;
      --cyan: #37c8d6;
      --blue: #2684ff;
      --amber: #f0ad3d;
      --red: #ff5b62;
      --green: #57d38c;
    }
    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    body {
      margin: 0;
      min-width: 320px;
      background:
        radial-gradient(circle at 15% 0%, #173040 0, transparent 34rem),
        var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
    header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
    .eyebrow { color: var(--cyan); font-weight: 700; letter-spacing: .12em; text-transform: uppercase; font-size: 12px; }
    h1 { margin: 6px 0 0; font-size: clamp(24px, 4vw, 42px); line-height: 1.05; }
    .subtitle { margin: 10px 0 0; color: var(--muted); max-width: 700px; }
    .run-state {
      display: flex; align-items: center; gap: 8px; white-space: nowrap;
      background: var(--panel); border: 1px solid var(--line); border-radius: 999px;
      padding: 8px 12px; color: var(--muted); font-size: 13px;
    }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--green); box-shadow: 0 0 14px var(--green); }
    .attack-banner {
      margin-top: 18px; padding: 10px 14px; border-left: 4px solid var(--red);
      background: color-mix(in srgb, var(--red) 13%, transparent); color: #ffdadd;
      font-weight: 700; display: none;
    }
    .attack-banner.active { display: block; }
    .controls { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
    button {
      appearance: none; border: 1px solid var(--line); border-radius: 8px;
      background: var(--panel-2); color: var(--text); font: inherit; font-weight: 700;
      padding: 10px 15px; cursor: pointer;
    }
    button.primary { background: var(--cyan); border-color: var(--cyan); color: #041014; }
    button:focus-visible { outline: 3px solid #fff; outline-offset: 2px; }
    .stage { display: grid; grid-template-columns: 1fr .62fr 1fr; gap: 18px; margin-top: 18px; align-items: stretch; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 18px; }
    .panel h2 { margin: 0; font-size: 17px; }
    .panel-kicker { color: var(--muted); margin-top: 4px; font-size: 13px; }
    .tank-wrap { display: grid; grid-template-columns: minmax(150px, 1fr) minmax(120px, .72fr); gap: 14px; align-items: center; margin-top: 12px; }
    .tank-svg { width: 100%; height: auto; max-height: 300px; }
    .tank-outline { fill: #0b151c; stroke: var(--muted); stroke-width: 4; }
    #water { fill: var(--blue); transition: y .45s linear, height .45s linear; }
    .threshold { stroke: var(--amber); stroke-width: 2; stroke-dasharray: 5 5; }
    .overflow-line { stroke: var(--red); stroke-width: 2; }
    .svg-label { fill: var(--muted); font-size: 12px; }
    .metric { margin: 16px 0; }
    .metric-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .metric-value { font-size: clamp(25px, 4vw, 38px); font-variant-numeric: tabular-nums; font-weight: 700; margin-top: 2px; }
    .metric-value.small { font-size: 24px; }
    .safe { color: var(--green); }
    .warn { color: var(--amber); }
    .danger { color: var(--red); }
    .flow { display: flex; flex-direction: column; justify-content: center; text-align: center; min-height: 330px; }
    .flow-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .wire-value {
      margin: 8px 0; background: #071016; border: 1px solid var(--line); border-radius: 8px;
      padding: 10px 8px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      color: var(--cyan); overflow-wrap: anywhere; font-size: 13px;
    }
    .arrow { color: var(--cyan); font-size: 30px; line-height: 1; }
    .arrow.return { transform: rotate(180deg); color: var(--amber); }
    .chart-panel { margin-top: 18px; }
    .chart-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 12px; }
    .legend { display: flex; flex-wrap: wrap; gap: 14px; color: var(--muted); font-size: 13px; }
    .legend span::before { content: ""; display: inline-block; width: 18px; height: 3px; margin-right: 6px; vertical-align: middle; background: currentColor; }
    .legend .true { color: var(--red); }
    .legend .reported { color: var(--cyan); }
    #trend { width: 100%; height: auto; display: block; margin-top: 10px; }
    .grid-line { stroke: var(--line); stroke-width: 1; }
    .axis-text { fill: var(--muted); font-size: 11px; }
    #true-path { fill: none; stroke: var(--red); stroke-width: 3; }
    #reported-path { fill: none; stroke: var(--cyan); stroke-width: 3; }
    .evidence-note { margin: 14px 0 0; color: var(--muted); font-size: 13px; }
    .evidence-note strong { color: var(--text); }
    @media (max-width: 820px) {
      .stage { grid-template-columns: 1fr 1fr; }
      .flow { grid-column: 1 / -1; grid-row: 2; min-height: 0; }
      .arrow { transform: rotate(90deg); }
      .arrow.return { transform: rotate(270deg); }
    }
    @media (max-width: 560px) {
      .shell { padding: 16px; }
      header { flex-direction: column; }
      .stage { grid-template-columns: 1fr; }
      .flow { grid-column: auto; grid-row: auto; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <div class="eyebrow">CS 6494 · CPS Evidence Lab</div>
        <h1>What does the controller know?</h1>
        <p class="subtitle">One control loop, two views of reality. Compare physical state with the observation crossing the cyber–physical boundary.</p>
      </div>
      <div class="run-state"><span class="dot"></span><span id="run-label">Connecting…</span></div>
    </header>

    <div id="attack-banner" class="attack-banner" role="status">Sensor observation has diverged from physical truth.</div>

    <div id="controls" class="controls" hidden>
      <button id="normal-button" class="primary" type="button">Run normal scenario</button>
      <button id="spoof-button" type="button">Run spoofed-sensor scenario</button>
    </div>

    <section class="stage" aria-label="Control loop state">
      <article class="panel">
        <h2>Physical process</h2>
        <div class="panel-kicker">Independent process-side observation</div>
        <div class="tank-wrap">
          <svg class="tank-svg" viewBox="0 0 210 280" role="img" aria-labelledby="tank-title tank-desc">
            <title id="tank-title">Modeled tank level</title>
            <desc id="tank-desc">The water fill height follows the true process level.</desc>
            <defs><clipPath id="tank-clip"><rect x="32" y="18" width="126" height="230" rx="10"/></clipPath></defs>
            <rect class="tank-outline" x="30" y="16" width="130" height="234" rx="12"/>
            <rect id="water" x="32" y="140" width="126" height="108" clip-path="url(#tank-clip)"/>
            <line class="threshold" x1="30" y1="75" x2="160" y2="75"/>
            <line class="overflow-line" x1="22" y1="56" x2="168" y2="56"/>
            <text class="svg-label" x="174" y="79">90</text>
            <text class="svg-label" x="174" y="60">100</text>
            <text class="svg-label" x="174" y="248">0%</text>
          </svg>
          <div>
            <div class="metric">
              <div class="metric-label">True level</div>
              <div id="true-level" class="metric-value">—</div>
            </div>
            <div class="metric">
              <div class="metric-label">Physical state</div>
              <div id="physical-state" class="metric-value small">—</div>
            </div>
          </div>
        </div>
      </article>

      <article class="panel flow">
        <div class="flow-label">Sensor observation</div>
        <div class="arrow">→</div>
        <div id="wire-observation" class="wire-value">waiting for data</div>
        <div class="arrow return">→</div>
        <div class="flow-label">Actuator command: <strong id="wire-command">—</strong></div>
      </article>

      <article class="panel">
        <h2>Controller / operator</h2>
        <div class="panel-kicker">What the cyber side can directly observe</div>
        <div class="metric">
          <div class="metric-label">Reported level</div>
          <div id="reported-level" class="metric-value">—</div>
        </div>
        <div class="metric">
          <div class="metric-label">Valve command</div>
          <div id="valve-command" class="metric-value small">—</div>
        </div>
        <div class="metric">
          <div class="metric-label">Apparent state</div>
          <div id="apparent-state" class="metric-value small">—</div>
        </div>
      </article>
    </section>

    <section class="panel chart-panel">
      <div class="chart-head">
        <div>
          <h2>Evidence over time</h2>
          <div class="panel-kicker">Level (% of nominal tank capacity)</div>
        </div>
        <div class="legend" aria-label="Chart legend"><span class="true">True level</span><span class="reported">Reported level</span></div>
      </div>
      <svg id="trend" viewBox="0 0 900 250" role="img" aria-labelledby="trend-title trend-desc">
        <title id="trend-title">True and reported tank level over time</title>
        <desc id="trend-desc">The two lines overlap in the normal scenario and diverge after sensor spoofing begins.</desc>
        <g id="chart-grid"></g>
        <path id="true-path"></path>
        <path id="reported-path"></path>
      </svg>
      <p class="evidence-note"><strong>Evidence boundary:</strong> the JSON message proves what crossed the network. It does not, by itself, prove the physical level.</p>
    </section>
  </main>
  <script>
    const canControl = __CAN_CONTROL__;
    const controlToken = __CONTROL_TOKEN__;
    const controls = document.getElementById('controls');
    if (canControl) controls.hidden = false;

    const pageBase = new URL(window.location.href);
    pageBase.search = '';
    pageBase.hash = '';
    if (!pageBase.pathname.endsWith('/')) pageBase.pathname += '/';
    const apiUrl = (path) => new URL(path, pageBase);

    function stateClass(value) {
      if (value === 'OVERFLOW') return 'danger';
      if (value === 'HIGH-HIGH' || value === 'WARNING') return 'warn';
      return 'safe';
    }

    function pathFor(history, key) {
      if (!history.length) return '';
      const left = 44, right = 884, top = 16, bottom = 220;
      const maxTime = Math.max(22, history[history.length - 1].time);
      return history.map((point, index) => {
        const x = left + (point.time / maxTime) * (right - left);
        const y = bottom - (Math.max(0, Math.min(120, point[key])) / 120) * (bottom - top);
        return `${index ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
    }

    function drawGrid() {
      const group = document.getElementById('chart-grid');
      const levels = [0, 45, 55, 90, 100, 120];
      group.innerHTML = levels.map((level) => {
        const y = 220 - (level / 120) * 204;
        return `<line class="grid-line" x1="44" y1="${y}" x2="884" y2="${y}"></line>` +
               `<text class="axis-text" x="37" y="${y + 4}" text-anchor="end">${level}</text>`;
      }).join('') + '<text class="axis-text" x="884" y="242" text-anchor="end">time →</text>';
    }

    function render(data) {
      const current = data.current;
      if (!current) return;
      document.getElementById('run-label').textContent = `${data.scenario.toUpperCase()} · ${current.time.toFixed(1)} s${data.running ? '' : ' · complete'}`;
      document.getElementById('true-level').textContent = `${current.true_level.toFixed(1)}%`;
      document.getElementById('reported-level').textContent = `${current.reported_level.toFixed(1)}%`;
      document.getElementById('valve-command').textContent = current.valve;
      document.getElementById('wire-command').textContent = current.valve;
      document.getElementById('physical-state').textContent = current.physical_state;
      document.getElementById('apparent-state').textContent = current.apparent_state;
      document.getElementById('wire-observation').textContent = JSON.stringify({sensor_level: current.reported_level});

      const physical = document.getElementById('physical-state');
      const apparent = document.getElementById('apparent-state');
      physical.className = `metric-value small ${stateClass(current.physical_state)}`;
      apparent.className = `metric-value small ${stateClass(current.apparent_state)}`;
      document.getElementById('attack-banner').classList.toggle('active', current.attack_active);

      const bounded = Math.max(0, Math.min(120, current.true_level));
      const height = (bounded / 120) * 230;
      const water = document.getElementById('water');
      water.setAttribute('y', 248 - height);
      water.setAttribute('height', height);
      document.getElementById('true-path').setAttribute('d', pathFor(data.history, 'true_level'));
      document.getElementById('reported-path').setAttribute('d', pathFor(data.history, 'reported_level'));
    }

    async function poll() {
      try {
        const response = await fetch(apiUrl('api/state'), {cache: 'no-store'});
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        render(await response.json());
      } catch (error) {
        document.getElementById('run-label').textContent = `Disconnected · ${error.message}`;
      }
    }

    async function startScenario(scenario) {
      await fetch(apiUrl('api/start'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Control-Token': controlToken},
        body: JSON.stringify({scenario})
      });
      await poll();
    }

    document.getElementById('normal-button').addEventListener('click', () => startScenario('normal'));
    document.getElementById('spoof-button').addEventListener('click', () => startScenario('spoof'));
    drawGrid();
    poll();
    setInterval(poll, 500);
  </script>
</body>
</html>
"""


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass
class Tank:
    """Minimal tank physics expressed in percentage points per second."""

    level: float = 50.0
    inlet_rate: float = 6.0
    drain_rate: float = 1.0
    maximum_level: float = 120.0

    def advance(self, valve: str, seconds: float) -> None:
        inflow = self.inlet_rate if valve == "OPEN" else 0.0
        self.level = clamp(
            self.level + (inflow - self.drain_rate) * seconds,
            0.0,
            self.maximum_level,
        )

    def sensor_reading(self, bias: float = 0.0) -> float:
        return clamp(self.level + bias, 0.0, 100.0)


@dataclass
class HysteresisController:
    """PLC stand-in: open below LOW, close above HIGH, otherwise hold."""

    low: float = LOW_LEVEL
    high: float = HIGH_LEVEL
    valve: str = "CLOSED"

    def decide(self, reported_level: float) -> Tuple[str, str]:
        if reported_level < self.low:
            self.valve = "OPEN"
            reason = f"below {self.low:.0f}%"
        elif reported_level > self.high:
            self.valve = "CLOSED"
            reason = f"above {self.high:.0f}%"
        else:
            reason = "inside band; hold"
        return self.valve, reason


@dataclass(frozen=True)
class Sample:
    elapsed: float
    true_level: float
    reported_level: float
    valve: str
    attack_active: bool


def physical_state(level: float) -> str:
    if level >= OVERFLOW_LEVEL:
        return "OVERFLOW"
    if level >= HIGH_HIGH_LEVEL:
        return "HIGH-HIGH"
    return "SAFE"


def apparent_state(reported_level: float) -> str:
    return "WARNING" if reported_level >= HIGH_HIGH_LEVEL else "SAFE"


def simulate(
    duration: float,
    tick: float = 1.0,
    spoof_after: Optional[float] = None,
    sensor_bias: float = -50.0,
    initial_level: float = 50.0,
) -> List[Sample]:
    """Run the same control loop without sockets or wall-clock delays."""

    tank = Tank(level=initial_level)
    controller = HysteresisController()
    samples: List[Sample] = []
    elapsed = 0.0
    while elapsed <= duration + 1e-9:
        attack_active = spoof_after is not None and elapsed >= spoof_after
        bias = sensor_bias if attack_active else 0.0
        reported = tank.sensor_reading(bias)
        valve, _ = controller.decide(reported)
        samples.append(
            Sample(elapsed, tank.level, reported, valve, attack_active)
        )
        tank.advance(valve, tick)
        elapsed += tick
    return samples


class WebSimulation:
    """Thread-safe shared simulation for browser viewers."""

    def __init__(
        self,
        duration: float,
        tick: float,
        speed: float,
        spoof_after: float,
        sensor_bias: float,
    ) -> None:
        self.duration = duration
        self.tick = tick
        self.speed = speed
        self.spoof_after = spoof_after
        self.sensor_bias = sensor_bias
        self.lock = threading.Lock()
        self.generation = 0
        self.running = False
        self.scenario = "normal"
        self.current: Optional[Dict[str, Any]] = None
        self.history: List[Dict[str, Any]] = []

    def start(self, scenario: str) -> None:
        if scenario not in {"normal", "spoof"}:
            raise ValueError("scenario must be normal or spoof")
        with self.lock:
            self.generation += 1
            generation = self.generation
            self.running = True
            self.scenario = scenario
            self.current = None
            self.history = []
        thread = threading.Thread(
            target=self._run,
            args=(generation, scenario),
            daemon=True,
        )
        thread.start()

    def _run(self, generation: int, scenario: str) -> None:
        tank = Tank()
        controller = HysteresisController()
        elapsed = 0.0
        while elapsed <= self.duration + 1e-9:
            with self.lock:
                if generation != self.generation:
                    return
            attack_active = scenario == "spoof" and elapsed >= self.spoof_after
            bias = self.sensor_bias if attack_active else 0.0
            reported = tank.sensor_reading(bias)
            valve, reason = controller.decide(reported)
            current = {
                "time": round(elapsed, 3),
                "true_level": round(tank.level, 3),
                "reported_level": round(reported, 3),
                "valve": valve,
                "decision": reason,
                "attack_active": attack_active,
                "physical_state": physical_state(tank.level),
                "apparent_state": apparent_state(reported),
            }
            with self.lock:
                if generation != self.generation:
                    return
                self.current = current
                self.history.append(current)
            tank.advance(valve, self.tick)
            elapsed += self.tick
            if elapsed <= self.duration + 1e-9:
                time.sleep(self.tick / self.speed)
        with self.lock:
            if generation == self.generation:
                self.running = False

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "scenario": self.scenario,
                "running": self.running,
                "current": dict(self.current) if self.current else None,
                "history": [dict(sample) for sample in self.history],
            }


def make_dashboard_handler(
    simulation: WebSimulation, control_token: str
) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def send_bytes(self, status: int, content_type: str, payload: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def send_json(self, status: int, value: Dict[str, Any]) -> None:
            payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
            self.send_bytes(status, "application/json; charset=utf-8", payload)

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            parsed = urlparse(self.path)
            if parsed.path.rstrip("/").endswith("/api/state"):
                self.send_json(200, simulation.snapshot())
                return

            supplied_token = parse_qs(parsed.query).get("token", [""])[0]
            can_control = secrets.compare_digest(supplied_token, control_token)
            page = DASHBOARD_HTML.replace(
                "__CAN_CONTROL__", "true" if can_control else "false"
            ).replace(
                "__CONTROL_TOKEN__", json.dumps(control_token if can_control else "")
            )
            self.send_bytes(200, "text/html; charset=utf-8", page.encode("utf-8"))

        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            parsed = urlparse(self.path)
            if not parsed.path.rstrip("/").endswith("/api/start"):
                self.send_json(404, {"error": "not found"})
                return
            supplied_token = self.headers.get("X-Control-Token", "")
            if not secrets.compare_digest(supplied_token, control_token):
                self.send_json(403, {"error": "presenter token required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                scenario = str(payload.get("scenario", ""))
                simulation.start(scenario)
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})
                return
            self.send_json(200, {"ok": True, "scenario": scenario})

        def log_message(self, format_string: str, *values: Any) -> None:
            if getattr(self.server, "verbose", False):
                super().log_message(format_string, *values)

    return DashboardHandler


def run_web(args: argparse.Namespace) -> int:
    token = args.control_token or secrets.token_urlsafe(9)
    simulation = WebSimulation(
        duration=args.duration,
        tick=args.tick,
        speed=args.speed,
        spoof_after=args.spoof_after,
        sensor_bias=args.sensor_bias,
    )
    simulation.start(args.scenario)
    handler = make_dashboard_handler(simulation, token)
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    server.verbose = args.verbose  # type: ignore[attr-defined]
    print("WEB VISUALIZATION", flush=True)
    print(f"Viewer:    http://127.0.0.1:{args.port}/", flush=True)
    print(f"Presenter: http://127.0.0.1:{args.port}/?token={token}", flush=True)
    print("For a SPHERE ingress, append the same ?token=... to the ingress URL.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb visualization stopped.", file=sys.stderr)
        return 130
    finally:
        server.server_close()
    return 0


def send_message(stream: Any, message: Dict[str, Any]) -> str:
    raw = json.dumps(message, separators=(",", ":"))
    stream.write(raw.encode("utf-8") + b"\n")
    stream.flush()
    return raw


def receive_message(stream: Any) -> Tuple[Optional[Dict[str, Any]], str]:
    line = stream.readline()
    if not line:
        return None, ""
    raw = line.decode("utf-8").rstrip("\r\n")
    return json.loads(raw), raw


def run_process(args: argparse.Namespace) -> int:
    spoof_after = args.spoof_after
    if args.scenario == "spoof" and spoof_after is None:
        spoof_after = 8.0

    tank = Tank(level=args.initial_level)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((args.bind, args.port))
        server.listen(1)
        print("PROCESS / physical truth", flush=True)
        print(f"Listening on {args.bind}:{args.port}; waiting for controller...", flush=True)
        connection, address = server.accept()
        print(f"Controller connected from {address[0]}:{address[1]}", flush=True)
        print(" time | true % | reported % | valve  | sensor  | physical state", flush=True)
        print("------+--------+------------+--------+---------+---------------", flush=True)

        with connection, connection.makefile("rwb") as stream:
            elapsed = 0.0
            attack_announced = False
            while elapsed <= args.duration + 1e-9:
                attack_active = spoof_after is not None and elapsed >= spoof_after
                if attack_active and not attack_announced:
                    print(
                        f"*** SENSOR SPOOF ACTIVE: reported = true {args.sensor_bias:+.0f}% ***",
                        flush=True,
                    )
                    attack_announced = True

                bias = args.sensor_bias if attack_active else 0.0
                reported = tank.sensor_reading(bias)
                observation = {
                    "type": "observation",
                    "time": round(elapsed, 3),
                    "sensor_level": round(reported, 3),
                }
                send_message(stream, observation)
                response, _ = receive_message(stream)
                if response is None:
                    print("Controller disconnected.", file=sys.stderr)
                    return 2
                if response.get("type") != "command" or response.get("valve") not in {
                    "OPEN",
                    "CLOSED",
                }:
                    raise ValueError(f"invalid controller response: {response!r}")

                valve = str(response["valve"])
                state = physical_state(tank.level)
                marker = " ***" if state != "SAFE" else ""
                sensor = "SPOOFED" if attack_active else "HONEST"
                print(
                    f"{elapsed:5.1f} | {tank.level:6.1f} | {reported:10.1f} | "
                    f"{valve:6} | {sensor:7} | {state}{marker}",
                    flush=True,
                )
                tank.advance(valve, args.tick)
                elapsed += args.tick
                if elapsed <= args.duration + 1e-9:
                    time.sleep(args.tick / args.speed)

            send_message(stream, {"type": "done"})
        return 0
    except KeyboardInterrupt:
        print("\nProcess stopped.", file=sys.stderr)
        return 130
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Process error: {error}", file=sys.stderr)
        return 2
    finally:
        server.close()


def connect_with_retry(host: str, port: int, timeout: float) -> socket.socket:
    deadline = time.monotonic() + timeout
    last_error: Optional[OSError] = None
    while time.monotonic() < deadline:
        try:
            return socket.create_connection((host, port), timeout=3.0)
        except OSError as error:
            last_error = error
            time.sleep(0.5)
    raise ConnectionError(f"could not connect to {host}:{port}: {last_error}")


def run_controller(args: argparse.Namespace) -> int:
    controller = HysteresisController(low=args.low, high=args.high)
    print("CONTROLLER / operator view", flush=True)
    print(f"Connecting to process at {args.host}:{args.port}...", flush=True)
    try:
        connection = connect_with_retry(args.host, args.port, args.connect_timeout)
        print("Connected.", flush=True)
        print(" time | sensor % | command | apparent state | decision", flush=True)
        print("------+----------+---------+----------------+------------------", flush=True)
        with connection, connection.makefile("rwb") as stream:
            while True:
                message, raw = receive_message(stream)
                if message is None:
                    print("Process disconnected.", file=sys.stderr)
                    return 2
                if args.show_wire:
                    print(f"WIRE <- {raw}", flush=True)
                if message.get("type") == "done":
                    print("Experiment complete.", flush=True)
                    return 0
                if message.get("type") != "observation":
                    raise ValueError(f"invalid process message: {message!r}")

                elapsed = float(message["time"])
                reported = float(message["sensor_level"])
                valve, reason = controller.decide(reported)
                command = {"type": "command", "valve": valve}
                raw_command = send_message(stream, command)
                if args.show_wire:
                    print(f"WIRE -> {raw_command}", flush=True)
                print(
                    f"{elapsed:5.1f} | {reported:8.1f} | {valve:7} | "
                    f"{apparent_state(reported):14} | {reason}",
                    flush=True,
                )
    except KeyboardInterrupt:
        print("\nController stopped.", file=sys.stderr)
        return 130
    except (ConnectionError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Controller error: {error}", file=sys.stderr)
        return 2


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def port_number(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("must be between 1 and 65535")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Two-process tank/controller demo for CPS evidence reasoning."
    )
    subparsers = parser.add_subparsers(dest="role", required=True)

    process = subparsers.add_parser("process", help="run the tank and sensor")
    process.add_argument("--scenario", choices=("normal", "spoof"), default="normal")
    process.add_argument("--bind", default="0.0.0.0", help="listen address")
    process.add_argument("--port", type=port_number, default=DEFAULT_PORT)
    process.add_argument("--duration", type=positive_float, default=22.0)
    process.add_argument("--tick", type=positive_float, default=1.0)
    process.add_argument(
        "--speed",
        type=positive_float,
        default=1.0,
        help="simulation speed multiplier (default: real time)",
    )
    process.add_argument("--initial-level", type=float, default=50.0)
    process.add_argument(
        "--spoof-after",
        type=float,
        default=None,
        help="seconds before spoofing starts (spoof scenario default: 8)",
    )
    process.add_argument(
        "--sensor-bias",
        type=float,
        default=-50.0,
        help="bias added to the true level while spoofing",
    )
    process.set_defaults(function=run_process)

    controller = subparsers.add_parser("controller", help="run the controller/HMI view")
    controller.add_argument("--host", default="127.0.0.1", help="process hostname")
    controller.add_argument("--port", type=port_number, default=DEFAULT_PORT)
    controller.add_argument("--low", type=float, default=LOW_LEVEL)
    controller.add_argument("--high", type=float, default=HIGH_LEVEL)
    controller.add_argument("--connect-timeout", type=positive_float, default=20.0)
    controller.add_argument(
        "--show-wire",
        action="store_true",
        help="show raw JSON observations and commands",
    )
    controller.set_defaults(function=run_controller)

    web = subparsers.add_parser(
        "web", help="serve a shared browser visualization of the complete loop"
    )
    web.add_argument("--scenario", choices=("normal", "spoof"), default="normal")
    web.add_argument("--bind", default="0.0.0.0", help="web listen address")
    web.add_argument("--port", type=port_number, default=8088)
    web.add_argument("--duration", type=positive_float, default=22.0)
    web.add_argument("--tick", type=positive_float, default=0.5)
    web.add_argument("--speed", type=positive_float, default=1.0)
    web.add_argument("--spoof-after", type=float, default=8.0)
    web.add_argument("--sensor-bias", type=float, default=-50.0)
    web.add_argument(
        "--control-token",
        default=None,
        help="presenter token (a random token is generated by default)",
    )
    web.add_argument("--verbose", action="store_true", help="log HTTP requests")
    web.set_defaults(function=run_web)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.role == "controller" and args.low >= args.high:
        parser.error("--low must be less than --high")
    return int(args.function(args))


if __name__ == "__main__":
    raise SystemExit(main())
