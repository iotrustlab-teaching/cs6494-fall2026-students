# If you want to take a deeper dive: where the GPS edit goes

This page is optional. It describes the **public-source local practice flight**:
ArduPilot Copter SITL controls an Iris drone in Gazebo. The practice route is a
small square over a generic runway. It is not the CTF2 stadium mission.

## Follow one measurement

```text
Gazebo drone position (simulator reference)
          │
          ▼
ArduPilot's simulated GPS sensor  ◀── attack.py requests an offset
          │                         through SIM_GPS1_GLTCH_X/Y
          ├── GPS_RAW_INT ──► student_watchdog.py
          │                         │
          ▼                         └── may request BRAKE or AUTO
ArduPilot position estimate                  │
          │                                  ▼
ArduPilot navigation and motors ◀──── flight-mode request
          │
          ▼
Gazebo moves the drone ──► next simulated sensor reading
```

Gazebo has a reference position for the simulated drone. ArduPilot uses that
world to generate sensor readings, including GPS. The local attack changes the
**GPS reading**, not Gazebo's reference position. The flight controller then
uses its sensor inputs to estimate where it is and decide how to fly. That may
eventually change where the simulated drone actually goes.

The runner saves three different tracks in each route plot:

1. **Simulator reference:** where the drone is in Gazebo's model.
2. **Reported GPS:** the position delivered as a GPS reading.
3. **Controller estimate:** ArduPilot's current position estimate.

These tracks need not agree during an attack. None is a measurement from a real
drone. The watchdog receives only the reported GPS message; it does not get the
simulator reference track.

## The two files your team edits

In `attack.py`, `AttackPlan` specifies when the GPS offset starts, how long it
lasts, its north/east direction, and its maximum ramp rate. For example:

```python
AttackPlan(start_s=25.0, hold_s=20.0,
           north_m=20.0, east_m=0.0, ramp_m_per_s=25.0)
```

The runner converts that offset from metres to latitude/longitude degrees and
sets ArduPilot SITL's `SIM_GPS1_GLTCH_X/Y` parameters. A parameter confirmation
means SITL accepted the setting. Check later GPS samples and the simulator
reference track before claiming the flight changed.

In `student_watchdog.py`, `Watchdog.update(gps_msg, now_monotonic)` receives each
fresh `GPS_RAW_INT` sample. The supplied watchdog compares the reported position
change with movement implied by the GPS speed and course. Its central decision
looks like this:

```python
if residual_m > threshold_m:
    return "BRAKE"
```

The returned word is a **request**. `runner.py` sends it to ArduPilot. A later
`mode_confirmed` event comes from the flight controller's heartbeat and shows
that the mode actually changed. Likewise, `AUTO` is a request to resume, not
proof that the mission completed. Check `mission_completed`, the route plot,
and the event trace together.

## What the four runs can tell you

Compare the same attack with the supplied watchdog and your revised watchdog.
Then run without an attack to see whether your revision interrupts ordinary
flight. A GPS jump may be easy to catch while a smooth drift may stay below a
jump threshold. A quiet interval does not necessarily mean the GPS position is
correct again. Those are design assumptions to test, not hidden answers.

This local exercise changes **SITL simulator parameters**. CTF2 uses a
different, private sensor-edit interface and arbiter. The local results teach
the sensor-to-decision loop, but they do not prove what would happen in the CTF2
stadium mission, on a physical drone, or under an actual RF/network attack.
