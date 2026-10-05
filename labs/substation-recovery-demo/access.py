from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from compiler import ControllerBuild, InterlockCompiler
from simulator import SubstationSimulator


CODE_ALPHABET = "ACDEFGHJKLMNPQRTUVWXYZ234679"
SESSION_TTL_SECONDS = 12 * 60 * 60
MAX_TOKENS_PER_STUDENT = 8
WORKSPACE_VERSION = 1
SUBMISSION_VERSION = 1
SUBMISSION_MAX_BYTES = 24_000


class AccessDenied(RuntimeError):
    pass


class DraftConflict(RuntimeError):
    def __init__(self, current_revision: int) -> None:
        super().__init__("submission draft changed in another browser; reload before editing")
        self.current_revision = current_revision


@dataclass(frozen=True)
class StudentIdentity:
    student_id: str
    label: str


@dataclass
class SessionRecord:
    token_hash: str
    student_id: str
    created_at: float
    last_seen: float


def normalize_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def hash_code(value: str) -> str:
    return hashlib.sha256(normalize_code(value).encode("ascii")).hexdigest()


def generate_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))
    return f"SRL-{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def create_roster(
    roster_path: Path,
    invites_path: Path,
    *,
    labels: list[str],
    overwrite: bool = False,
) -> list[dict[str, str]]:
    if not labels:
        raise ValueError("at least one student label is required")
    if (roster_path.exists() or invites_path.exists()) and not overwrite:
        raise FileExistsError("roster or invitation file already exists")

    entries: list[dict[str, str]] = []
    invitations: list[dict[str, str]] = []
    used_ids: set[str] = set()
    for index, raw_label in enumerate(labels, start=1):
        label = raw_label.strip() or f"Student {index:02d}"
        student_id = _unique_student_id(label, used_ids, fallback=f"student-{index:02d}")
        used_ids.add(student_id)
        code = generate_code()
        entries.append({"studentId": student_id, "label": label, "codeHash": hash_code(code)})
        invitations.append({"student_id": student_id, "label": label, "access_code": code})

    roster_path.parent.mkdir(parents=True, exist_ok=True)
    invites_path.parent.mkdir(parents=True, exist_ok=True)
    roster_payload = {
        "version": 1,
        "createdAtUnixMs": int(time.time() * 1000),
        "students": entries,
    }
    _atomic_write(roster_path, json.dumps(roster_payload, indent=2) + "\n", 0o600)

    _write_invitations(invites_path, invitations)
    return invitations


def append_roster(
    roster_path: Path,
    invites_path: Path,
    *,
    labels: list[str],
) -> list[dict[str, str]]:
    if not labels:
        raise ValueError("at least one student label is required")
    if not roster_path.exists() or not invites_path.exists():
        raise FileNotFoundError("both the existing roster and invitation file are required")

    roster_payload = json.loads(roster_path.read_text(encoding="utf-8"))
    entries = roster_payload.get("students")
    if roster_payload.get("version") != 1 or not isinstance(entries, list):
        raise ValueError("unsupported student roster format")

    with invites_path.open(newline="", encoding="utf-8-sig") as handle:
        invitations = list(csv.DictReader(handle))

    roster_by_id: dict[str, dict[str, str]] = {}
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("invalid student roster entry")
        student_id = str(raw_entry.get("studentId", ""))
        label = str(raw_entry.get("label", ""))
        code_hash = str(raw_entry.get("codeHash", ""))
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", student_id)
            or not label
            or not re.fullmatch(r"[a-f0-9]{64}", code_hash)
            or student_id in roster_by_id
        ):
            raise ValueError("invalid or duplicate roster entry")
        roster_by_id[student_id] = raw_entry

    invites_by_id: dict[str, dict[str, str]] = {}
    for invitation in invitations:
        student_id = str(invitation.get("student_id", ""))
        label = str(invitation.get("label", ""))
        code = str(invitation.get("access_code", ""))
        if student_id in invites_by_id or student_id not in roster_by_id:
            raise ValueError("invitation list does not match the server roster")
        roster_entry = roster_by_id[student_id]
        if label != roster_entry["label"] or hash_code(code) != roster_entry["codeHash"]:
            raise ValueError("an existing invitation does not match the server roster")
        invites_by_id[student_id] = invitation

    if set(invites_by_id) != set(roster_by_id):
        raise ValueError("invitation list does not match the server roster")

    used_ids = set(roster_by_id)
    used_labels = {str(entry["label"]) for entry in entries}
    new_entries: list[dict[str, str]] = []
    new_invitations: list[dict[str, str]] = []
    used_hashes = {str(entry["codeHash"]) for entry in entries}
    for index, raw_label in enumerate(labels, start=1):
        label = raw_label.strip()
        if not label:
            raise ValueError("student labels cannot be blank when appending")
        if label in used_labels:
            raise ValueError(f"student label already exists: {label}")
        student_id = _unique_student_id(label, used_ids, fallback=f"student-{len(entries) + index:02d}")
        used_ids.add(student_id)
        used_labels.add(label)
        code = generate_code()
        code_hash = hash_code(code)
        while code_hash in used_hashes:
            code = generate_code()
            code_hash = hash_code(code)
        used_hashes.add(code_hash)
        new_entries.append({"studentId": student_id, "label": label, "codeHash": code_hash})
        new_invitations.append({"student_id": student_id, "label": label, "access_code": code})

    roster_payload["students"] = entries + new_entries
    roster_payload["updatedAtUnixMs"] = int(time.time() * 1000)
    _atomic_write(roster_path, json.dumps(roster_payload, indent=2) + "\n", 0o600)
    _write_invitations(invites_path, invitations + new_invitations)
    return new_invitations


def _unique_student_id(label: str, used_ids: set[str], *, fallback: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or fallback
    student_id = base
    suffix = 2
    while student_id in used_ids:
        student_id = f"{base}-{suffix}"
        suffix += 1
    return student_id


def _write_invitations(path: Path, invitations: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["student_id", "label", "access_code"])
        writer.writeheader()
        writer.writerows(invitations)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _atomic_write(path: Path, value: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.chmod(temporary, mode)
    os.replace(temporary, path)


class LoginLimiter:
    def __init__(self, *, max_failures: int = 8, window_seconds: int = 300) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, peer: str) -> bool:
        now = time.monotonic()
        with self._lock:
            failures = self._failures[peer]
            while failures and now - failures[0] > self.window_seconds:
                failures.popleft()
            return len(failures) < self.max_failures

    def failed(self, peer: str) -> None:
        with self._lock:
            self._failures[peer].append(time.monotonic())

    def succeeded(self, peer: str) -> None:
        with self._lock:
            self._failures.pop(peer, None)


class StudentLab:
    def __init__(self, identity: StudentIdentity, compiler: Any, workspace_root: Path) -> None:
        self.identity = identity
        self.compiler = compiler
        self.workspace_dir = workspace_root / identity.student_id
        self.workspace_file = self.workspace_dir / "workspace.json"
        self.submission_file = self.workspace_dir / "submission.json"
        self._lock = threading.RLock()
        build = self._load_build()
        self.simulator = SubstationSimulator(build, run_prefix=identity.student_id)

    def close(self) -> None:
        self.simulator.stop()

    def compile(self, source: str) -> ControllerBuild:
        with self._lock:
            build = self.compiler.compile(source)
            self.simulator.activate_build(build)
            self._save_workspace(build)
            return build

    def compile_preset(self, preset: str) -> ControllerBuild:
        with self._lock:
            build = self.compiler.compile_preset(preset)
            self.simulator.activate_build(build)
            self._save_workspace(build)
            return build

    def snapshot(self, after_seq: int | None = None) -> dict[str, Any]:
        payload = self.simulator.snapshot(after_seq=after_seq)
        payload["student"] = self.public_identity()
        return payload

    def wait_for_events(self, after_seq: int, timeout_seconds: float) -> dict[str, Any]:
        payload = self.simulator.wait_for_events(after_seq, timeout_seconds)
        payload["student"] = self.public_identity()
        return payload

    def public_identity(self) -> dict[str, str]:
        return {"studentId": self.identity.student_id, "label": self.identity.label}

    def workspace_payload(self) -> dict[str, Any]:
        state = self.simulator.snapshot()
        build = self.compiler.load(state["build"]["buildId"])
        return {
            "activeBuildId": build.build_id,
            "activeSource": build.source,
            "activePreset": build.manifest.get("preset"),
        }

    def submission_payload(self) -> dict[str, Any]:
        with self._lock:
            record = self._load_submission_record()
            return {
                "draft": record.get("draft"),
                "revision": int(record.get("revision", 0)),
                "updatedAtUnixMs": record.get("updatedAtUnixMs"),
            }

    def save_submission(self, draft: Any, base_revision: Any) -> dict[str, Any]:
        if not isinstance(base_revision, int) or isinstance(base_revision, bool) or base_revision < 0:
            raise ValueError("baseRevision must be a non-negative integer")
        validated = self._validate_submission(draft)
        with self._lock:
            current = self._load_submission_record()
            current_revision = int(current.get("revision", 0))
            if base_revision != current_revision:
                raise DraftConflict(current_revision)
            updated_at = int(time.time() * 1000)
            record = {
                "version": SUBMISSION_VERSION,
                "studentId": self.identity.student_id,
                "revision": current_revision + 1,
                "updatedAtUnixMs": updated_at,
                "draft": validated,
            }
            _atomic_write(self.submission_file, json.dumps(record, indent=2) + "\n")
            return {
                "draft": validated,
                "revision": record["revision"],
                "updatedAtUnixMs": updated_at,
            }

    def _load_build(self) -> ControllerBuild:
        if self.workspace_file.exists():
            try:
                payload = json.loads(self.workspace_file.read_text(encoding="utf-8"))
                return self.compiler.load(str(payload["activeBuildId"]))
            except (KeyError, ValueError, json.JSONDecodeError, RuntimeError):
                pass
        build = self.compiler.compile_preset("vulnerable")
        self._save_workspace(build)
        return build

    def _save_workspace(self, build: ControllerBuild) -> None:
        payload = {
            "version": WORKSPACE_VERSION,
            "studentId": self.identity.student_id,
            "activeBuildId": build.build_id,
            "activeSourceSha256": build.source_sha256,
            "updatedAtUnixMs": int(time.time() * 1000),
        }
        _atomic_write(self.workspace_file, json.dumps(payload, indent=2) + "\n")

    def _load_submission_record(self) -> dict[str, Any]:
        if not self.submission_file.exists():
            return {"version": SUBMISSION_VERSION, "revision": 0, "draft": None}
        try:
            payload = json.loads(self.submission_file.read_text(encoding="utf-8"))
            if (
                payload.get("version") != SUBMISSION_VERSION
                or payload.get("studentId") != self.identity.student_id
                or not isinstance(payload.get("revision"), int)
            ):
                raise ValueError("invalid submission record")
            if payload.get("draft") is not None:
                payload["draft"] = self._validate_submission(payload["draft"])
            return payload
        except (OSError, ValueError, json.JSONDecodeError):
            return {"version": SUBMISSION_VERSION, "revision": 0, "draft": None}

    @staticmethod
    def _validate_submission(draft: Any) -> dict[str, Any]:
        if not isinstance(draft, dict) or draft.get("version") != SUBMISSION_VERSION:
            raise ValueError("unsupported submission draft")
        if set(draft) - {"version", "fields", "capturedTests", "repair", "updatedAt"}:
            raise ValueError("submission draft contains unsupported fields")
        fields = draft.get("fields")
        captured = draft.get("capturedTests")
        repair = draft.get("repair")
        updated_at = draft.get("updatedAt")
        if not isinstance(fields, dict) or len(fields) > 64:
            raise ValueError("submission fields are invalid")
        if any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or len(key) > 80
            or len(value) > 5_000
            for key, value in fields.items()
        ):
            raise ValueError("submission field value is invalid")
        if not isinstance(captured, dict) or len(captured) > 8:
            raise ValueError("captured test records are invalid")
        if any(not isinstance(key, str) or not isinstance(value, dict) for key, value in captured.items()):
            raise ValueError("captured test record is invalid")
        if repair is not None and not isinstance(repair, dict):
            raise ValueError("captured repair is invalid")
        if updated_at is not None and not isinstance(updated_at, str):
            raise ValueError("submission timestamp is invalid")
        encoded = json.dumps(draft, separators=(",", ":"), ensure_ascii=True)
        if len(encoded.encode("utf-8")) > SUBMISSION_MAX_BYTES:
            raise ValueError("submission draft is too large")
        return json.loads(encoded)


class StudentAccessManager:
    def __init__(
        self,
        roster_path: Path,
        compiler: Any,
        workspace_root: Path,
        *,
        max_active_labs: int = 64,
        compiler_factory: Callable[[StudentIdentity], Any] | None = None,
    ) -> None:
        payload = json.loads(roster_path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("students"), list):
            raise ValueError("unsupported student roster format")
        self.compiler = compiler
        self.workspace_root = workspace_root
        self.max_active_labs = max_active_labs
        self.compiler_factory = compiler_factory or (lambda _identity: self.compiler)
        self._identities: dict[str, StudentIdentity] = {}
        self._students_by_code: dict[str, str] = {}
        for item in payload["students"]:
            identity = StudentIdentity(str(item["studentId"]), str(item["label"]))
            code_hash = str(item["codeHash"])
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", identity.student_id):
                raise ValueError("student IDs must use lowercase letters, numbers, and hyphens")
            if (
                not re.fullmatch(r"[a-f0-9]{64}", code_hash)
                or identity.student_id in self._identities
                or code_hash in self._students_by_code
            ):
                raise ValueError("invalid or duplicate roster entry")
            self._identities[identity.student_id] = identity
            self._students_by_code[code_hash] = identity.student_id
        self._sessions: dict[str, SessionRecord] = {}
        self._student_tokens: dict[str, deque[str]] = defaultdict(deque)
        self._labs: dict[str, StudentLab] = {}
        self._lock = threading.RLock()
        self.login_limiter = LoginLimiter()

    @property
    def student_count(self) -> int:
        return len(self._identities)

    def login(self, access_code: str, peer: str) -> tuple[str, StudentLab]:
        if not self.login_limiter.allow(peer):
            raise AccessDenied("too many failed attempts; wait five minutes and try again")
        student_id = self._students_by_code.get(hash_code(access_code))
        if not student_id:
            self.login_limiter.failed(peer)
            raise AccessDenied("access code not recognized")
        self.login_limiter.succeeded(peer)
        with self._lock:
            lab = self._lab_locked(student_id)
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
            now = time.time()
            self._sessions[token_hash] = SessionRecord(token_hash, student_id, now, now)
            student_tokens = self._student_tokens[student_id]
            for existing_hash in list(student_tokens):
                existing = self._sessions.get(existing_hash)
                if not existing or now - existing.last_seen > SESSION_TTL_SECONDS:
                    self._sessions.pop(existing_hash, None)
                    student_tokens.remove(existing_hash)
            student_tokens.append(token_hash)
            while len(student_tokens) > MAX_TOKENS_PER_STUDENT:
                self._sessions.pop(student_tokens.popleft(), None)
            return token, lab

    def resolve(self, token: str | None) -> StudentLab | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = time.time()
        with self._lock:
            record = self._sessions.get(token_hash)
            if not record:
                return None
            if now - record.last_seen > SESSION_TTL_SECONDS:
                self._drop_session_locked(token_hash, record.student_id)
                return None
            record.last_seen = now
            return self._lab_locked(record.student_id)

    def logout(self, token: str | None) -> None:
        if not token:
            return
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            record = self._sessions.get(token_hash)
            if record:
                self._drop_session_locked(token_hash, record.student_id)

    def close(self) -> None:
        with self._lock:
            labs = list(self._labs.values())
            self._labs.clear()
            self._sessions.clear()
            self._student_tokens.clear()
        for lab in labs:
            lab.close()

    def _lab_locked(self, student_id: str) -> StudentLab:
        lab = self._labs.get(student_id)
        if lab:
            return lab
        if len(self._labs) >= self.max_active_labs:
            raise AccessDenied("the class service is at capacity; ask the instructor to retry shortly")
        identity = self._identities[student_id]
        lab = StudentLab(identity, self.compiler_factory(identity), self.workspace_root)
        self._labs[student_id] = lab
        return lab

    def _drop_session_locked(self, token_hash: str, student_id: str) -> None:
        self._sessions.pop(token_hash, None)
        tokens = self._student_tokens.get(student_id)
        if tokens:
            try:
                tokens.remove(token_hash)
            except ValueError:
                pass
