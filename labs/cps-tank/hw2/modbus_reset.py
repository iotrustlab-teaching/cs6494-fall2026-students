#!/usr/bin/env python3
"""Restore the fixed HW2 OpenPLC controller to its disclosed CLOSED baseline."""

from __future__ import annotations

from modbus_tank_run import FixedOpenPLCClient, initialize_controller


def main() -> int:
    client = FixedOpenPLCClient()
    try:
        client.connect()
        initialize_controller(client)
    finally:
        client.close()
    print("reset complete: OpenPLC inlet baseline is CLOSED; evidence was retained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
