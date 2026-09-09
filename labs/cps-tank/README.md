# CPS Tank Micro-Lab

A software-only cyber-physical security demo. It needs **Python 3 and nothing else** — no packages
to install, no accounts, no testbed access.

The tank process owns the **true water level**. The controller never sees that. It receives only a
**reported sensor level**, and applies a PLC-style hysteresis rule:

```text
reported level < 45%  -> OPEN inlet valve
reported level > 55%  -> CLOSE inlet valve
otherwise             -> hold the previous command
```

In the attack run, the sensor starts reporting a value 50 percentage points below the truth. The
controller keeps making the *correct decision for its input* — but its input no longer represents
the process. The tank overflows while every piece of evidence the controller can see still says
safe.

That gap, between what a system can observe and what is physically true, is the thing this course
is about.

## Run it

Open two terminals in this directory. **Start the process first.**

Terminal A — the physical process:

```bash
python3 cps_tank.py process --scenario normal
```

Terminal B — the controller and operator view:

```bash
python3 cps_tank.py controller
```

The normal run stays below the 90% high-high threshold and cycles the valve. Now repeat with the
spoofed sensor.

Terminal A:

```bash
python3 cps_tank.py process --scenario spoof
```

Terminal B:

```bash
python3 cps_tank.py controller --show-wire
```

At 8 simulated seconds the process announces the spoof. At 18 seconds the true level crosses 100% —
while the controller sees 54% and is still commanding the inlet valve open.

On Windows use `py -3` instead of `python3`.

Your instructor may also share a **viewer URL** showing the same run in a browser. That is for
watching together; the two-terminal run above is what you should do yourself.

## What each view can actually establish

This table is the point of the exercise. Be precise about which view proves what.

| View | Direct evidence | It does **not** establish |
| --- | --- | --- |
| Process | true modeled state, received actuator command, sensor transformation | what the controller received or believed |
| Controller | received sensor claim, control decision, transmitted command | the true physical state |
| `--show-wire` | bytes exchanged between the two programs | that the sensor claim is physically accurate |

The wire log is deliberately plain JSON:

```json
{"type":"observation","time":18.0,"sensor_level":54.0}
```

That packet establishes that the network carried **a claim of 54%**. It does not establish that the
tank was at 54%. Keep that distinction — it is the difference between evidence and belief, and it is
what the rest of the course builds on.

## Running it across two machines

The same file works unchanged across two hosts. On host `a`:

```bash
python3 cps_tank.py process --scenario spoof
```

On host `b`:

```bash
python3 cps_tank.py controller --host a --show-wire
```

Substitute `a`'s IP address if the hostname does not resolve. No code changes are needed. Later in
the course you will run exactly this across two testbed nodes.

## Troubleshooting

- **`Address already in use`** — stop the previous run, or give both commands the same alternate
  port: `--port 55050`
- **`could not connect`** — start the process side first, check the hostname, and make sure the port
  is reachable between the two hosts
- **Slow startup** — the controller retries for 20 seconds; extend with `--connect-timeout 60`
- **Want it faster** — add `--speed 10` to the process command
- **Stopping** — Ctrl-C either side. This demo controls no physical hardware.
