from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from compiler import InterlockCompiler


OPENPLC_IMAGE = (
    "ghcr.io/iotrustlab-teaching/openplc-v3"
    "@sha256:ba613b4b00a3561e0acc0caf884c2187d5c008023625989b89c6006d4af3aaf1"
)
OPENPLC_UPSTREAM_REVISION = "b5d41356dab4aeadca0dd7ca64ba542f870b595d"
OPENPLC_SCAN_MS = 50
MODBUS_UNIT_ID = 1


@dataclass(frozen=True)
class RegisterPoint:
    name: str
    iec_location: str
    modbus_address: int
    owner: str
    description: str


REGISTER_MAP = (
    RegisterPoint("request_seq", "%MW0", 1024, "adapter", "nonzero request sequence"),
    RegisterPoint("actual_positions", "%MW1", 1025, "adapter", "B0/S1/S2/S3 position bit mask"),
    RegisterPoint("target_mask", "%MW2", 1026, "adapter", "requested close target bit mask"),
    RegisterPoint("out_of_service_mask", "%MW3", 1027, "adapter", "declared OOS branch bit mask"),
    RegisterPoint("trip_latched", "%MW4", 1028, "adapter", "0 clear, 1 latched"),
    RegisterPoint("present_current_dA", "%MW5", 1029, "adapter", "present source current in deciamps"),
    RegisterPoint("current_limit_dA", "%MW6", 1030, "adapter", "teaching current limit in deciamps"),
    RegisterPoint("decision_code", "%MW7", 1031, "controller", "0 deny, 1 allow"),
    RegisterPoint("decision_seq", "%MW8", 1032, "controller", "sequence associated with decision"),
    RegisterPoint("heartbeat", "%MW9", 1033, "controller", "increments on each controller scan"),
)


def register_manifest() -> list[dict[str, Any]]:
    return [asdict(point) for point in REGISTER_MAP]


def render_openplc_program(student_source: str) -> str:
    """Bind the student function to the fixed HW2-style OpenPLC Modbus image."""

    source = student_source.replace("\r\n", "\n").strip() + "\n"
    InterlockCompiler._validate_source(source)
    return source + r'''

PROGRAM SubstationController
VAR
    RequestSeq AT %MW0 : UINT := 0;
    ActualPositionsInput AT %MW1 : UINT := 0;
    TargetMaskInput AT %MW2 : UINT := 0;
    OutOfServiceMaskInput AT %MW3 : UINT := 0;
    TripLatchedInput AT %MW4 : UINT := 0;
    PresentCurrentInput_dA AT %MW5 : UINT := 0;
    CurrentLimitInput_dA AT %MW6 : UINT := 400;
    DecisionCode AT %MW7 : UINT := 0;
    DecisionSeq AT %MW8 : UINT := 0;
    Heartbeat AT %MW9 : UINT := 0;
END_VAR
VAR
    PermitClose : BOOL := FALSE;
END_VAR

IF RequestSeq <> DecisionSeq THEN
    PermitClose := CloseInterlock(
        CloseRequested := TRUE,
        ActualPositions := UINT_TO_BYTE(ActualPositionsInput),
        TargetMask := UINT_TO_BYTE(TargetMaskInput),
        OutOfServiceMask := UINT_TO_BYTE(OutOfServiceMaskInput),
        TripLatched := TripLatchedInput <> 0,
        PresentCurrent_dA := PresentCurrentInput_dA,
        CurrentLimit_dA := CurrentLimitInput_dA
    );
    IF PermitClose THEN
        DecisionCode := 1;
    ELSE
        DecisionCode := 0;
    END_IF;
    DecisionSeq := RequestSeq;
END_IF;

Heartbeat := Heartbeat + 1;
END_PROGRAM

CONFIGURATION Config0
    RESOURCE Res0 ON PLC
        TASK Main(INTERVAL := T#50ms, PRIORITY := 0);
        PROGRAM Inst0 WITH Main : SubstationController;
    END_RESOURCE
END_CONFIGURATION
'''


def openplc_program_identity(student_source: str) -> dict[str, Any]:
    program = render_openplc_program(student_source)
    return {
        "programSha256": hashlib.sha256(program.encode("utf-8")).hexdigest(),
        "runtimeImage": OPENPLC_IMAGE,
        "runtimeRevision": OPENPLC_UPSTREAM_REVISION,
        "scanMs": OPENPLC_SCAN_MS,
        "modbusUnitId": MODBUS_UNIT_ID,
        "registerMap": register_manifest(),
    }
