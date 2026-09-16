#!/usr/bin/env python3
"""Build a readable, offline Modbus representation of each simulated scan."""

from __future__ import annotations

from typing import List


NETWORK_FIELDS = [
    "elapsed_s",
    "transaction_id",
    "plane",
    "source",
    "destination",
    "protocol",
    "function_code",
    "operation",
    "object",
    "address",
    "value",
    "authority",
    "accepted",
]


def scan_records(
    elapsed: float,
    transaction_start: int,
    honest_level: float,
    delivered_level: float,
    valve_open: bool,
    attack_active: bool,
) -> List[dict]:
    """Describe owner-to-peer operations without contacting a live controller."""

    records = [
        {
            "elapsed_s": f"{elapsed:.3f}",
            "transaction_id": transaction_start,
            "plane": "process_data",
            "source": "bridge",
            "destination": "process-plc",
            "protocol": "Modbus/TCP",
            "function_code": 3,
            "operation": "read_holding_registers",
            "object": "reported_level_pct",
            "address": "2048:2",
            "value": f"{honest_level:.3f}",
            "authority": "owner_to_peer_shuttle",
            "accepted": "true",
        }
    ]
    transaction = transaction_start + 1
    if attack_active:
        records.append(
            {
                "elapsed_s": f"{elapsed:.3f}",
                "transaction_id": transaction,
                "plane": "process_data",
                "source": "course-inline-filter",
                "destination": "bridge-buffer",
                "protocol": "local policy hook",
                "function_code": "n/a",
                "operation": "replace_whitelisted_value",
                "object": "reported_level_pct",
                "address": "2048:2",
                "value": f"{delivered_level:.3f}",
                "authority": "isolated_course_attack_role",
                "accepted": "true",
            }
        )
        transaction += 1
    records.extend(
        [
            {
                "elapsed_s": f"{elapsed:.3f}",
                "transaction_id": transaction,
                "plane": "process_data",
                "source": "bridge",
                "destination": "controller-plc",
                "protocol": "Modbus/TCP",
                "function_code": 16,
                "operation": "write_multiple_registers",
                "object": "reported_level_pct",
                "address": "2048:2",
                "value": f"{delivered_level:.3f}",
                "authority": "owner_to_peer_shuttle",
                "accepted": "true",
            },
            {
                "elapsed_s": f"{elapsed:.3f}",
                "transaction_id": transaction + 1,
                "plane": "process_data",
                "source": "bridge",
                "destination": "controller-plc",
                "protocol": "Modbus/TCP",
                "function_code": 1,
                "operation": "read_coils",
                "object": "inlet_valve_open",
                "address": "0:1",
                "value": str(valve_open).lower(),
                "authority": "owner_to_peer_shuttle",
                "accepted": "true",
            },
            {
                "elapsed_s": f"{elapsed:.3f}",
                "transaction_id": transaction + 2,
                "plane": "process_data",
                "source": "bridge",
                "destination": "process-plc",
                "protocol": "Modbus/TCP",
                "function_code": 15,
                "operation": "write_multiple_coils",
                "object": "inlet_valve_open",
                "address": "0:1",
                "value": str(valve_open).lower(),
                "authority": "owner_to_peer_shuttle",
                "accepted": "true",
            },
        ]
    )
    return records
