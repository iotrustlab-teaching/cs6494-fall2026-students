from __future__ import annotations

import argparse
import csv
from pathlib import Path

from access import append_roster, create_roster


ROOT = Path(__file__).resolve().parent
DEFAULT_ROSTER = ROOT / "runtime" / "access" / "roster.json"
DEFAULT_INVITES = ROOT / "runtime" / "access" / "student-invites.csv"


def labels_from_csv(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("the roster CSV is empty")
    field = "label" if "label" in rows[0] else "name" if "name" in rows[0] else None
    if not field:
        raise ValueError("the roster CSV needs a label or name column")
    return [str(row.get(field, "")).strip() for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create private Substation Recovery Lab access codes")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--count", type=int, help="number of anonymous student workspaces")
    source.add_argument("--csv", type=Path, help="CSV with a label or name column")
    parser.add_argument("--prefix", default="Student", help="label prefix used with --count")
    parser.add_argument("--start", type=int, default=1, help="first label number used with --count")
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    parser.add_argument("--invites", type=Path, default=DEFAULT_INVITES)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--append", action="store_true", help="verify and extend an existing roster")
    args = parser.parse_args()

    if args.append and args.overwrite:
        parser.error("--append and --overwrite cannot be used together")
    if args.start < 1:
        parser.error("--start must be at least 1")

    if args.count is not None:
        if not 1 <= args.count <= 500:
            parser.error("--count must be between 1 and 500")
        labels = [
            f"{args.prefix} {index:02d}"
            for index in range(args.start, args.start + args.count)
        ]
    else:
        labels = labels_from_csv(args.csv)

    if args.append:
        invitations = append_roster(args.roster, args.invites, labels=labels)
        action = "Added"
    else:
        invitations = create_roster(args.roster, args.invites, labels=labels, overwrite=args.overwrite)
        action = "Created"
    print(f"{action} {len(invitations)} private student workspaces.")
    print(f"Invitation list: {args.invites}")
    print(f"Server roster: {args.roster}")


if __name__ == "__main__":
    main()
