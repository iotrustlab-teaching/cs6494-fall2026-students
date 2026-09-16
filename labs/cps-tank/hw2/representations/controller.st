(**
  Teaching-sized IEC 61131-3 Structured Text representation of the same
  stateful controller used by the Python and C artifacts.

  %MD0 is two Modbus holding registers (2048-2049) carrying one REAL.
  %QX0.0 is Modbus coil 0. These are lab-local addresses, not a claim that
  every PLC or the full SWaT controller uses this compact map.
**)
PROGRAM HW2TankController
VAR
    reported_level_pct AT %MD0 : REAL;
    inlet_valve_open AT %QX0.0 : BOOL := FALSE;
END_VAR

VAR
    LOW_LEVEL_PCT : REAL := 45.0;
    HIGH_LEVEL_PCT : REAL := 55.0;
END_VAR

IF reported_level_pct < LOW_LEVEL_PCT THEN
    inlet_valve_open := TRUE;
ELSIF reported_level_pct > HIGH_LEVEL_PCT THEN
    inlet_valve_open := FALSE;
END_IF;
END_PROGRAM

CONFIGURATION Config0
    RESOURCE Res0 ON PLC
        TASK Main(INTERVAL := T#50ms, PRIORITY := 0);
        PROGRAM Inst0 WITH Main : HW2TankController;
    END_RESOURCE
END_CONFIGURATION
