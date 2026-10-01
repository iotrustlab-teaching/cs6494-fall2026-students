from __future__ import annotations

import argparse
import json
import mimetypes
import signal
import sys
import threading
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from access import AccessDenied, StudentAccessManager, StudentLab, create_roster
from compiler import CompileError, InterlockCompiler, PresetLibrary
from openplc_runtime import DockerOpenPLCRuntimePool
from simulator import SCENARIOS


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"
MAX_JSON_BYTES = 32_000
DEFAULT_ROSTER = ROOT / "runtime" / "access" / "roster.json"
DEFAULT_INVITES = ROOT / "runtime" / "access" / "student-invites.csv"
DEFAULT_WORKSPACES = ROOT / "runtime" / "students"
DEFAULT_OPENPLC_ROOT = ROOT / "runtime" / "openplc"


class LiveApplication:
    def __init__(
        self,
        roster_path: Path = DEFAULT_ROSTER,
        workspace_root: Path = DEFAULT_WORKSPACES,
        *,
        max_active_labs: int = 64,
        secure_cookies: bool = False,
        controller_backend: str = "native",
        openplc_root: Path = DEFAULT_OPENPLC_ROOT,
        openplc_start_port: int = 15020,
    ) -> None:
        self.compiler = InterlockCompiler() if controller_backend == "native" else PresetLibrary()
        self.openplc_pool: DockerOpenPLCRuntimePool | None = None
        compiler_factory = None
        if controller_backend == "openplc":
            self.openplc_pool = DockerOpenPLCRuntimePool(
                openplc_root,
                start_port=openplc_start_port,
            )
            compiler_factory = lambda identity: self.openplc_pool.compiler_for(identity.student_id)
        self.access = StudentAccessManager(
            roster_path,
            self.compiler,
            workspace_root,
            max_active_labs=max_active_labs,
            compiler_factory=compiler_factory,
        )
        self.secure_cookies = secure_cookies
        self.controller_mode = (
            "OPENPLC V3 COMPILED ST RUNTIME"
            if controller_backend == "openplc"
            else "MATIEC-COMPILED ST FUNCTION"
        )
        self.protocol_mode = (
            "INTERNAL MODBUS HANDSHAKE; IEC-104 NOT ACTIVE"
            if controller_backend == "openplc"
            else "BROWSER ADAPTER; IEC-104 NOT ACTIVE"
        )

    def close(self) -> None:
        self.access.close()


class LiveRequestHandler(BaseHTTPRequestHandler):
    server_version = "SubstationRecoveryLab/0.2"
    protocol_version = "HTTP/1.1"

    @property
    def app(self) -> LiveApplication:
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if parsed.path == "/api/health":
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "mode": "LIVE SIMULATION",
                    "controllerMode": self.app.controller_mode,
                    "protocolMode": self.app.protocol_mode,
                    "accessMode": "PRIVATE STUDENT SESSIONS",
                    "agentMode": "DISABLED; BOUNDED PROPOSAL HOOK RESERVED",
                },
            )
            return
        if parsed.path == "/api/session":
            lab = self._student_lab()
            self._json(
                HTTPStatus.OK,
                {
                    "authenticated": lab is not None,
                    "student": lab.public_identity() if lab else None,
                    "sessionTtlHours": 12,
                },
            )
            return
        if not parsed.path.startswith("/api/"):
            self._serve_static(parsed.path)
            return

        lab = self._student_lab()
        if not lab:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "student session required"})
            return
        if parsed.path == "/api/state":
            query = parse_qs(parsed.query)
            after = self._query_int(query, "after", None)
            wait = self._query_int(query, "wait", 0)
            if after is not None and wait:
                payload = lab.wait_for_events(after, timeout_seconds=min(15, max(1, wait)))
            else:
                payload = lab.snapshot(after_seq=after)
            self._json(HTTPStatus.OK, payload)
            return
        if parsed.path == "/api/presets":
            sources = self.app.compiler.preset_sources()
            self._json(
                HTTPStatus.OK,
                {
                    "presets": [{"id": name, "source": source} for name, source in sources.items()],
                    "scenarios": [{"id": key, **value} for key, value in SCENARIOS.items()],
                    "workspace": lab.workspace_payload(),
                },
            )
            return
        if parsed.path == "/api/evidence":
            self._json(HTTPStatus.OK, lab.snapshot())
            return
        if parsed.path == "/api/agent/status":
            self._json(
                HTTPStatus.OK,
                {
                    "enabled": False,
                    "mode": "disabled",
                    "boundary": "A future local agent may propose source or bounded requests inside this student session only.",
                    "mayExecute": False,
                },
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            self._require_same_origin()
            payload = self._read_json()
            if parsed.path == "/api/session/login":
                access_code = payload.get("accessCode")
                if not isinstance(access_code, str) or not 6 <= len(access_code) <= 80:
                    raise ValueError("enter a valid access code")
                token, lab = self.app.access.login(access_code, self.client_address[0])
                cookie = f"lab_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200"
                if self.app.secure_cookies:
                    cookie += "; Secure"
                self._json(
                    HTTPStatus.OK,
                    {"authenticated": True, "student": lab.public_identity(), "sessionTtlHours": 12},
                    extra_headers={"Set-Cookie": cookie},
                )
                return
            if parsed.path == "/api/session/logout":
                self.app.access.logout(self._session_token())
                cookie = "lab_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
                if self.app.secure_cookies:
                    cookie += "; Secure"
                self._json(
                    HTTPStatus.OK,
                    {"authenticated": False},
                    extra_headers={"Set-Cookie": cookie},
                )
                return

            lab = self._student_lab()
            if not lab:
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "student session required"})
                return
            if parsed.path == "/api/reset":
                result = lab.simulator.reset(
                    scenario=str(payload.get("scenario", "s3_fault")),
                    initial_positions=payload.get("positions") or {},
                )
                result["student"] = lab.public_identity()
                self._json(HTTPStatus.OK, result)
                return
            if parsed.path == "/api/commands":
                result = lab.simulator.submit_command(
                    action=str(payload.get("action", "")),
                    device=str(payload.get("device", "")),
                    authority=str(payload.get("authority", "manual")),
                )
                self._json(HTTPStatus.ACCEPTED, result)
                return
            if parsed.path == "/api/builds/compile":
                source = payload.get("source")
                if not isinstance(source, str):
                    raise ValueError("source must be a string")
                build = lab.compile(source)
                self._json(
                    HTTPStatus.CREATED,
                    {
                        "status": "compile_clean",
                        "buildId": build.build_id,
                        "sourceSha256": build.source_sha256,
                        "manifest": build.manifest,
                    },
                )
                return
            if parsed.path == "/api/builds/preset":
                preset = str(payload.get("preset", ""))
                build = lab.compile_preset(preset)
                self._json(
                    HTTPStatus.OK,
                    {
                        "status": "compile_clean",
                        "preset": preset,
                        "buildId": build.build_id,
                        "sourceSha256": build.source_sha256,
                    },
                )
                return
            if parsed.path == "/api/tests/run":
                result = lab.simulator.run_test(str(payload.get("testId", "")))
                self._json(HTTPStatus.ACCEPTED, result)
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except CompileError as exc:
            self._json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": str(exc), "diagnostics": exc.diagnostics, "status": "compile_error"},
            )
        except AccessDenied as exc:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except (ValueError, RuntimeError) as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"internal error: {exc}"})

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (STATIC_ROOT / relative).resolve()
        try:
            candidate.relative_to(STATIC_ROOT.resolve())
        except ValueError:
            self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
            return
        if not candidate.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") or mime == "application/javascript" else mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self) -> dict:
        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            raise ValueError("Content-Type must be application/json")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_JSON_BYTES:
            raise ValueError("invalid JSON request size")
        raw = self.rfile.read(length)
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def _json(self, status: HTTPStatus, payload: dict, *, extra_headers: dict[str, str] | None = None) -> None:
        content = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(content)

    def _session_token(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        morsel = cookie.get("lab_session")
        return morsel.value if morsel else None

    def _student_lab(self) -> StudentLab | None:
        return self.app.access.resolve(self._session_token())

    def _require_same_origin(self) -> None:
        fetch_site = self.headers.get("Sec-Fetch-Site", "")
        if fetch_site == "cross-site":
            raise AccessDenied("cross-site request rejected")
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if origin and host and urlparse(origin).netloc != host:
            raise AccessDenied("request origin does not match this lab")

    @staticmethod
    def _query_int(query: dict[str, list[str]], name: str, default: int | None) -> int | None:
        try:
            return int(query.get(name, [str(default)])[0]) if query.get(name) else default
        except ValueError:
            return default

    def log_message(self, fmt: str, *args: object) -> None:
        if self.path.startswith("/api/state"):
            return
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")


class LiveHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: LiveApplication) -> None:
        super().__init__(address, LiveRequestHandler)
        self.app = app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Substation Recovery Lab")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    parser.add_argument("--workspaces", type=Path, default=DEFAULT_WORKSPACES)
    parser.add_argument("--max-active-labs", type=int, default=64)
    parser.add_argument("--secure-cookies", action="store_true")
    parser.add_argument("--controller-backend", choices=("native", "openplc"), default="native")
    parser.add_argument("--openplc-root", type=Path, default=DEFAULT_OPENPLC_ROOT)
    parser.add_argument("--openplc-start-port", type=int, default=15020)
    args = parser.parse_args()

    if not args.roster.exists():
        create_roster(
            args.roster,
            DEFAULT_INVITES,
            labels=["Instructor preview"],
        )
        print(f"Created preview access code list: {DEFAULT_INVITES}", flush=True)

    app = LiveApplication(
        args.roster,
        args.workspaces,
        max_active_labs=args.max_active_labs,
        secure_cookies=args.secure_cookies,
        controller_backend=args.controller_backend,
        openplc_root=args.openplc_root,
        openplc_start_port=args.openplc_start_port,
    )
    server = LiveHTTPServer((args.host, args.port), app)
    stopping = threading.Event()

    def stop_server(_signum: int, _frame: object) -> None:
        if stopping.is_set():
            return
        stopping.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop_server)
    signal.signal(signal.SIGTERM, stop_server)
    print(f"Substation Recovery Lab: http://{args.host}:{args.port}", flush=True)
    print(f"Mode: LIVE SIMULATION + {app.controller_mode}; {app.protocol_mode}", flush=True)
    print(f"Access: {app.access.student_count} private student workspace(s)", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        app.close()


if __name__ == "__main__":
    main()
