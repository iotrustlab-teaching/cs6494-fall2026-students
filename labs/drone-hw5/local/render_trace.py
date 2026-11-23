#!/usr/bin/env python3
"""Render one HW5 SITL JSONL trace as a self-contained SVG route receipt.

This is a teaching view, not a physical flight reconstruction. It keeps the
simulator's reference position separate from the GPS value and the flight
controller's estimate. Only confirmed mode changes are drawn as solid markers.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path


EARTH_RADIUS_M = 6_371_000.0
COLORS = {"truth": "#176b55", "gps": "#c53438", "estimate": "#2459a7"}
LABELS = {
    "truth": "Simulator reference position",
    "gps": "GPS reported to controller",
    "estimate": "Controller position estimate",
}


def read_trace(path: Path) -> list[dict]:
    events: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"{path}:{line_no}: expected a JSON object")
        events.append(event)
    if not events:
        raise ValueError(f"{path}: no events")
    return events


def finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def points_by_kind(events: list[dict]) -> dict[str, list[tuple[float, float, float]]]:
    result: dict[str, list[tuple[float, float, float]]] = {name: [] for name in COLORS}
    for event in events:
        kind = event.get("kind")
        if kind not in result:
            continue
        lat = finite_float(event.get("latitude_deg"))
        lon = finite_float(event.get("longitude_deg"))
        time_s = finite_float(event.get("t_s"))
        if lat is None or lon is None or time_s is None:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        result[kind].append((time_s, lat, lon))
    return result


def latest_at(points: list[tuple[float, float, float]], t: float) -> tuple[float, float] | None:
    latest = None
    for sample_time, lat, lon in points:
        if sample_time <= t:
            latest = (lat, lon)
        else:
            break
    return latest


def render(events: list[dict], title: str, source_name: str) -> str:
    traces = points_by_kind(events)
    all_points = [point for series in traces.values() for point in series]
    if not all_points:
        raise ValueError("trace has no valid truth, gps, or estimate positions")
    origin_lat, origin_lon = all_points[0][1:]
    cos_lat = max(0.01, abs(math.cos(math.radians(origin_lat))))

    def meters(lat: float, lon: float) -> tuple[float, float]:
        north = math.radians(lat - origin_lat) * EARTH_RADIUS_M
        east = math.radians(lon - origin_lon) * EARTH_RADIUS_M * cos_lat
        return east, north

    projected = {
        kind: [(t, *meters(lat, lon)) for t, lat, lon in series]
        for kind, series in traces.items()
    }
    xs = [east for series in projected.values() for _, east, _ in series]
    ys = [north for series in projected.values() for _, _, north in series]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 10.0)
    padding = max(5.0, span * 0.12)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    half = span / 2 + padding
    left, top, size = 80.0, 150.0, 590.0

    def xy(east: float, north: float) -> tuple[float, float]:
        return (left + (east - (center_x - half)) / (2 * half) * size,
                top + ((center_y + half) - north) / (2 * half) * size)

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 850" '
        'role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(title)}</title>',
        '<desc id="desc">Three separate simulated flight traces: simulator reference '
        'position, reported GPS, and controller estimate. Right panel lists event '
        'timing and evidence limits.</desc>',
        '<rect width="1120" height="850" fill="#f8fafc"/>',
        '<rect x="0" y="0" width="1120" height="10" fill="#aa0820"/>',
        f'<text x="52" y="65" font-family="Arial,sans-serif" font-size="31" '
        f'font-weight="700" fill="#16243a">{html.escape(title)}</text>',
        f'<text x="52" y="94" font-family="Arial,sans-serif" font-size="14" '
        f'fill="#536274">Source: {html.escape(source_name)} · local simulation</text>',
        '<rect x="80" y="150" width="590" height="590" rx="8" '
        'fill="#fff" stroke="#d3dce7" stroke-width="2"/>',
    ]
    for fraction in (0.25, 0.5, 0.75):
        coordinate = left + size * fraction
        parts.append(f'<path d="M {coordinate:.1f} {top:.1f} V {top+size:.1f} '
                     f'M {left:.1f} {top+size*fraction:.1f} H {left+size:.1f}" '
                     'stroke="#e7ebf0" stroke-width="1"/>')
    parts += [
        '<text x="606" y="729" font-family="Arial,sans-serif" font-size="13" '
        'fill="#536274">East →</text>',
        '<text x="94" y="174" font-family="Arial,sans-serif" font-size="13" '
        'fill="#536274">↑ North</text>',
        f'<text x="88" y="765" font-family="Arial,sans-serif" font-size="13" '
        f'fill="#536274">Width ≈ {2*half:.0f} m</text>',
    ]

    for kind in ("truth", "estimate", "gps"):
        series = projected[kind]
        if len(series) >= 2:
            coords = " ".join(f"{xy(e, n)[0]:.1f},{xy(e, n)[1]:.1f}"
                              for _, e, n in series)
            dash = ' stroke-dasharray="8 5"' if kind == "gps" else ""
            parts.append(f'<polyline points="{coords}" fill="none" '
                         f'stroke="{COLORS[kind]}" stroke-width="3"{dash} '
                         f'stroke-linejoin="round" stroke-linecap="round"/>')
        elif series:
            _, e, n = series[0]
            px, py = xy(e, n)
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" '
                         f'fill="{COLORS[kind]}"/>')

    timeline: list[str] = []
    mark_count = 0
    for event in events:
        kind = event.get("kind")
        if kind not in {"attack_request", "mode_request", "mode_confirmed",
                        "flight_finished", "error"}:
            continue
        t = finite_float(event.get("t_s"))
        if t is None:
            continue
        if kind == "attack_request":
            label = (f"GPS edit requested: N={finite_float(event.get('north_m')) or 0:.1f} m, "
                     f"E={finite_float(event.get('east_m')) or 0:.1f} m")
            icon, color = "A", "#bd2330"
        elif kind == "mode_request":
            label = f"Mode requested: {event.get('mode', '?')}"
            icon, color = "?", "#b26a05"
        elif kind == "mode_confirmed":
            label = f"Mode observed: {event.get('mode', '?')}"
            icon, color = "M", "#19714f"
        elif kind == "flight_finished":
            label, icon, color = "Flight disarmed; inspect mission result", "F", "#2459a7"
        else:
            label = f"Runner error: {event.get('message', '?')}"
            icon, color = "!", "#bd2330"
        if len(timeline) < 14:
            timeline.append(f"{t:.1f}s  {label}")
        location = latest_at(traces["truth"], t)
        if location and mark_count < 12 and kind in {"attack_request", "mode_confirmed", "error"}:
            px, py = xy(*meters(*location))
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="11" '
                         f'fill="#fff" stroke="{color}" stroke-width="2"/>')
            parts.append(f'<text x="{px:.1f}" y="{py+4:.1f}" text-anchor="middle" '
                         f'font-family="Arial,sans-serif" font-weight="700" font-size="11" '
                         f'fill="{color}">{icon}</text>')
            mark_count += 1

    parts.append('<text x="720" y="160" font-family="Arial,sans-serif" '
                 'font-size="20" font-weight="700" fill="#16243a">What the traces mean</text>')
    for index, kind in enumerate(("truth", "gps", "estimate")):
        y = 195 + index * 32
        parts.append(f'<line x1="720" y1="{y}" x2="758" y2="{y}" '
                     f'stroke="{COLORS[kind]}" stroke-width="4"/>')
        parts.append(f'<text x="770" y="{y+5}" font-family="Arial,sans-serif" '
                     f'font-size="15" fill="#25334b">{LABELS[kind]} '
                     f'({len(traces[kind])} samples)</text>')
    parts.append('<text x="720" y="310" font-family="Arial,sans-serif" '
                 'font-size="20" font-weight="700" fill="#16243a">Selected events</text>')
    for index, item in enumerate(timeline):
        safe = html.escape(item)
        if len(safe) > 52:
            safe = safe[:49] + "…"
        parts.append(f'<text x="720" y="{345+index*24}" font-family="Arial,sans-serif" '
                     f'font-size="12" fill="#344157">{safe}</text>')
    parts += [
        '<rect x="52" y="782" width="1016" height="48" rx="8" fill="#e8eef5"/>',
        '<text x="68" y="803" font-family="Arial,sans-serif" font-size="13" '
        'fill="#25334b">A requested GPS edit or mode is not proof it took effect. '
        'Check parameter confirmations, reported samples, and observed modes in JSONL.</text>',
        '<text x="68" y="820" font-family="Arial,sans-serif" font-size="12" '
        'fill="#536274">Simulator reference is model truth, not a real drone measurement. '
        'This chart alone does not establish mission success.</text>',
        '</svg>',
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="runner JSONL output")
    parser.add_argument("--output", type=Path, help="output SVG; default: trace.svg")
    parser.add_argument("--title", default="HW5 local flight route")
    args = parser.parse_args()
    output = args.output or args.trace.with_suffix(".svg")
    output.write_text(render(read_trace(args.trace), args.title,
                             args.trace.name), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
