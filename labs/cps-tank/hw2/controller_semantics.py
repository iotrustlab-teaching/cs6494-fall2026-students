#!/usr/bin/env python3
"""Language-independent reference semantics for the HW2 hysteresis controller."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


LOW_LEVEL_PCT = 45.0
HIGH_LEVEL_PCT = 55.0


@dataclass
class ControllerState:
    """The only retained controller state: the inlet-valve command."""

    inlet_valve_open: bool = False


def step_controller(
    reported_level_pct: float,
    state: ControllerState,
    low: float = LOW_LEVEL_PCT,
    high: float = HIGH_LEVEL_PCT,
) -> bool:
    """Execute one scan and return the stateful inlet-valve command.

    Strict comparisons are intentional. At either threshold the prior command
    is retained, which is why equivalence must be checked over sequences.
    """

    if reported_level_pct < low:
        state.inlet_valve_open = True
    elif reported_level_pct > high:
        state.inlet_valve_open = False
    return state.inlet_valve_open


def run_sequence(
    reported_levels: Iterable[float],
    initially_open: bool = False,
    low: float = LOW_LEVEL_PCT,
    high: float = HIGH_LEVEL_PCT,
) -> List[bool]:
    state = ControllerState(initially_open)
    return [step_controller(value, state, low, high) for value in reported_levels]
