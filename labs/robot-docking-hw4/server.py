#!/usr/bin/env python3
"""Loopback-only classroom view of the same Python/RTAMT HW4 engine."""

from __future__ import annotations

import argparse
import json
import math
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from hw4_core import compare_records, load_policy, replay_record, run_case, write_record
from reference_spec import SAFETY_FORMULA, SERVICE_FORMULA

HERE = Path(__file__).parent
MAX_BODY = 1_000_000


def compare_saved_runs(request: dict, folder: Path) -> dict:
    """Compare two server-saved runs by ID without reserializing their float traces in JS."""
    if set(request) != {"first_run_id", "second_run_id"}:
        raise ValueError("comparison needs first_run_id and second_run_id")
    first_id, second_id = request["first_run_id"], request["second_run_id"]
    if not all(isinstance(run_id, str) and re.fullmatch(r"[0-9a-f]{16}", run_id)
               for run_id in (first_id, second_id)):
        raise ValueError("comparison needs two valid run IDs")
    if first_id == second_id:
        raise ValueError("choose two different runs")
    records = []
    for run_id in (first_id, second_id):
        path = folder / f"run_{run_id}.json"
        if not path.is_file():
            raise ValueError(f"saved run {run_id} was not found; run it again or use hw4.py compare-runs")
        record = json.loads(path.read_text())
        if record.get("run_id") != run_id:
            raise ValueError("saved run ID does not match its filename")
        records.append(record)
    return compare_records(*records)


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, status: int, body: bytes, content_type: str,
                   filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if filename is not None:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, data: dict) -> None:
        self.send_bytes(status, json.dumps(data, allow_nan=False).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in {"/", "/index.html"}:
            self.send_bytes(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/app.js":
            self.send_bytes(200, (HERE / "app.js").read_bytes(), "text/javascript; charset=utf-8")
        elif path == "/style.css":
            self.send_bytes(200, (HERE / "style.css").read_bytes(), "text/css; charset=utf-8")
        elif path == "/api/status":
            try:
                self.send_json(200, {"engine": "Python model + RTAMT", "policy": load_policy(HERE / "policy.json"),
                                     "formulae": {"service": SERVICE_FORMULA, "safety": SAFETY_FORMULA},
                                     "sampling": "1 s, discrete, 0–7 s; no interpolation"})
            except (ValueError, OSError, json.JSONDecodeError) as error:
                self.send_json(500, {"error": str(error)})
        elif path.startswith("/api/download/"):
            run_id = path.removeprefix("/api/download/")
            if not re.fullmatch(r"[0-9a-f]{16}", run_id):
                self.send_json(400, {"error": "invalid run ID"})
                return
            filename = f"run_{run_id}.json"
            saved = HERE / "runs" / filename
            if not saved.is_file():
                self.send_json(404, {"error": "run not found"})
                return
            self.send_bytes(200, saved.read_bytes(), "application/json; charset=utf-8",
                            filename=f"hw4_{filename}")
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in {"/api/run", "/api/replay", "/api/compare-runs"}:
            self.send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("request body must be 1–1,000,000 bytes")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            if path == "/api/run":
                if set(data) != {"cruise_speed_m_s", "braking_m_s2"}:
                    raise ValueError("run accepts only cruise_speed_m_s and braking_m_s2")
                for value in data.values():
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        raise ValueError("scenario values must be finite numbers")
                record = run_case(**data, policy=load_policy(HERE / "policy.json"))
                write_record(HERE / "runs" / f"run_{record['run_id']}.json", record)
                self.send_json(200, record)
            elif path == "/api/replay":
                proof = replay_record(data)
                write_record(HERE / "runs" / f"run_{proof['replayed_run_id']}.json",
                             proof["replayed_run"])
                self.send_json(200, proof)
            else:
                self.send_json(200, compare_saved_runs(data, HERE / "runs"))
        except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024–65535")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"HW4 demo: http://127.0.0.1:{args.port}/", flush=True)
    print("Loopback only. Each Run resets the Python model and invokes RTAMT.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
