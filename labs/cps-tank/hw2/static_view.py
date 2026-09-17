#!/usr/bin/env python3
"""Run Clang CFG and Frama-C dependency analyses; normalize their raw output."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
BLOCK = re.compile(r"^\s*\[(B\d+)(?: \((ENTRY|EXIT)\))?\]\s*$")
SUCCESSORS = re.compile(r"^\s*Succs \(\d+\):\s*(.*)$")
FRAMAC_FUNCTION = re.compile(r"\[from\] Function controller_step:\n((?:  [^\n]*\n)+)")
FRAMAC_ROW = re.compile(r"^  (\S+) FROM (.+)$", re.M)


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    combined = result.stdout + result.stderr
    if result.returncode:
        raise RuntimeError(f"analysis command failed ({result.returncode}): {' '.join(command)}\n{combined}")
    return combined


def version(command: str) -> str:
    result = subprocess.run([command, "--version"], capture_output=True, text=True, check=False)
    return (result.stdout or result.stderr).strip().splitlines()[0]


def clang_binary() -> str:
    candidate = os.environ.get("HW2_CLANG") or shutil.which("clang-14") or shutil.which("clang")
    if not candidate:
        raise RuntimeError("Clang is required for CFG generation (install clang or set HW2_CLANG)")
    return candidate


def framac_binary() -> str | None:
    candidate = os.environ.get("HW2_FRAMAC") or shutil.which("frama-c")
    if candidate:
        return candidate
    provisioned = pathlib.Path("/opt/cs6494/frama-c-bundle/bin/frama-c")
    return str(provisioned) if provisioned.is_file() else None


def parse_clang_cfg(dump: str) -> tuple[str, list[dict]]:
    blocks: list[dict] = []
    current: dict | None = None
    for line in dump.splitlines():
        header = BLOCK.match(line)
        if header:
            current = {"id": header.group(1), "kind": header.group(2), "lines": [], "successors": []}
            blocks.append(current)
            continue
        if current is None:
            continue
        successor = SUCCESSORS.match(line)
        if successor:
            current["successors"] = re.findall(r"B\d+", successor.group(1))
        elif line.strip() and not line.lstrip().startswith("Preds "):
            current["lines"].append(line.strip())
    if not any(block["kind"] == "ENTRY" for block in blocks) or not any(
        block["kind"] == "EXIT" for block in blocks
    ):
        raise ValueError("Clang did not emit the expected controller_step CFG")
    identifiers = {block["id"] for block in blocks}
    if any(next_id not in identifiers for block in blocks for next_id in block["successors"]):
        raise ValueError("Clang CFG contains an unresolved successor")
    lines = ["digraph controller_step {", "  rankdir=TB;", "  node [shape=box, fontname=monospace];"]
    for block in blocks:
        label = block["id"] + (" (" + block["kind"].lower() + ")" if block["kind"] else "")
        if block["lines"]:
            label += "\n" + "\n".join(block["lines"])
        shape = "oval" if block["kind"] else "box"
        lines.append(f'  {block["id"]} [label={json.dumps(label)}, shape={shape}];')
    for block in blocks:
        for index, next_id in enumerate(block["successors"]):
            branch = "true" if index == 0 else "false"
            suffix = f' [label="{branch}"]' if len(block["successors"]) == 2 else ""
            lines.append(f'  {block["id"]} -> {next_id}{suffix};')
    lines.append("}")
    return "\n".join(lines) + "\n", blocks


def parse_framac_dependencies(raw: str) -> dict:
    section = FRAMAC_FUNCTION.search(raw)
    if section is None:
        raise ValueError("Frama-C did not report controller_step dependencies")
    rows = {match.group(1): match.group(2).strip() for match in FRAMAC_ROW.finditer(section.group(1))}
    if "state" not in rows or "\\result" not in rows:
        raise ValueError("Frama-C controller_step dependency rows are incomplete")
    if "reported_level_pct" not in rows["state"]:
        raise ValueError("Frama-C did not establish the reported-level dependency")
    return {
        "state_row": rows["state"],
        "result_row": rows["\\result"],
        "retains_previous_state": "(and SELF)" in rows["state"],
    }


def harness_for(source: pathlib.Path, raw_dir: pathlib.Path) -> pathlib.Path:
    default = HERE / "representations" / "controller.c"
    harness = HERE / "representations" / "framac_harness.c"
    target = raw_dir / "framac_harness.c"
    if source.resolve() == default.resolve():
        target.write_text(harness.read_text())
        return target
    escaped = str(source.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    target.write_text(harness.read_text().replace('"controller.c"', f'"{escaped}"'))
    return target


def generate(output: pathlib.Path, source_path: pathlib.Path | None = None,
             require_framac: bool = False) -> pathlib.Path:
    source = (source_path or HERE / "representations" / "controller.c").resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / "raw"
    raw_dir.mkdir(exist_ok=True)
    clang = clang_binary()
    clang_command = [clang, "-std=c11", "--analyze", "-o", os.devnull,
                     "-Xclang", "-analyze-function=controller_step",
                     "-Xclang", "-analyzer-checker=debug.DumpCFG", str(source)]
    clang_raw = run(clang_command)
    (raw_dir / "clang_cfg.txt").write_text(clang_raw)
    dot, blocks = parse_clang_cfg(clang_raw)
    (output / "controller_cfg.dot").write_text(dot)
    dot_binary = shutil.which("dot")
    if dot_binary:
        subprocess.run([dot_binary, "-Tsvg", str(output / "controller_cfg.dot"),
                        "-o", str(output / "controller_cfg.svg")], check=True)

    frama = framac_binary()
    if require_framac and frama is None:
        raise RuntimeError("Frama-C is required for dependency analysis on SPHERE")
    dependencies = None
    frama_command = None
    if frama:
        harness = harness_for(source, raw_dir)
        frama_command = [frama, "-eva", "-deps", "-eva-slevel", "100",
                         f"-cpp-extra-args=-I{source.parent}", str(harness)]
        frama_raw = run(frama_command)
        (raw_dir / "framac_dependencies.txt").write_text(frama_raw)
        dependencies = parse_framac_dependencies(frama_raw)
        if re.search(r"\b[1-9]\d* alarms? generated", frama_raw):
            raise RuntimeError("Frama-C reported analysis alarms; inspect raw/framac_dependencies.txt")
    else:
        for stale in ("framac_harness.c", "framac_dependencies.txt"):
            stale_file = raw_dir / stale
            if stale_file.exists():
                stale_file.unlink()

    contract = json.loads((HERE / "representations" / "controller_contract.json").read_text())
    observation = next(item for item in contract["variables"] if item["concept"] == "reported process observation")
    actuator = next(item for item in contract["variables"] if item["concept"] == "retained actuator decision")
    result = {
        "analysis_method": {"cfg": "Clang Static Analyzer debug.DumpCFG",
                            "dependencies": "Frama-C Eva and -deps" if dependencies else "unavailable"},
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "cfg_blocks": [{"id": block["id"], "successors": block["successors"]} for block in blocks],
        "external_observation": observation["c"],
        "actuator_decision": actuator["c"],
        "framac_dependencies": dependencies,
        "retained_state": actuator["c"] if dependencies and dependencies["retains_previous_state"] else None,
        "dependency_status": "analyzed" if dependencies else "Frama-C unavailable; no dependency claim",
        "mapping_source": "representations/controller_contract.json (names only, not analysis)",
        "limitation": "A possible source dependency does not prove a live packet, feasible attack, or physical consequence.",
    }
    (output / "dependency_map.json").write_text(json.dumps(result, indent=2) + "\n")
    provenance = [
        "# Toolchain for this analysis", "",
        f"- Source: `{source}` (SHA-256 `{result['source_sha256']}`)",
        f"- Clang: `{version(clang)}`", f"- CFG command: `{' '.join(clang_command)}`",
        "- Raw CFG: `raw/clang_cfg.txt`; DOT/SVG are projections of Clang blocks and successor edges.",
    ]
    if frama and frama_command:
        provenance += [f"- Frama-C: `{version(frama)}`",
                       f"- Dependency command: `{' '.join(frama_command)}`",
                       "- Raw Eva/dependencies: `raw/framac_dependencies.txt`; the exact harness is `raw/framac_harness.c`; `SELF` is Frama-C's retained-value indicator.",
                       "- Harness: initialized valve state in {0,1}; reported level in [0,100]; no claim for values outside that model."]
    else:
        provenance += ["- Frama-C: unavailable; dependency fields are intentionally unverified."]
    provenance += ["", "Clang CFG shows possible source-level control flow, not paths actually taken.",
                   "Frama-C's dependency result is an over-approximation under the documented harness.",
                   "Neither tool analyzes the ST compiler, Modbus packets, or tank physics.\n"]
    (output / "TOOLCHAIN.md").write_text("\n".join(provenance))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=HERE / "runs" / "analysis")
    parser.add_argument("--source", type=pathlib.Path,
                        default=HERE / "representations" / "controller.c")
    parser.add_argument("--require-framac", action="store_true",
                        help="fail instead of producing a CFG-only result")
    args = parser.parse_args()
    try:
        print(generate(args.out, args.source, args.require_framac or bool(os.environ.get("HW2_INSTANCE_ID"))))
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"analysis failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
