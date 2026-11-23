# HW5 public-source local flight candidate

**Release status: HOLD until an end-to-end Docker flight has run and its trace
has been reviewed.** This folder is a complete candidate for a team-local
practice exercise. It uses a real ArduPilot Copter SITL flight controller and
the Gazebo Harmonic Iris world. It does **not** contain the private CTF2
server, its campus stadium mission, its GPS edit arbiter, or staff credentials.

## What the four cases do

The practice mission takes off, follows a 30 m square, and returns to launch.
The attack changes the simulated GPS sensor's reported position by up to 20 m
north during the AUTO flight. The edit is made via ArduPilot SITL's
`SIM_GPS1_GLTCH_X/Y` parameters. These are **simulator controls**, not network
packets to a GPS receiver. The flight controller still consumes the affected
GPS sensor data. `student_watchdog.py` observes `GPS_RAW_INT` only; simulator
truth is recorded separately for later assessment.

| Case | GPS edit | Watchdog |
| --- | --- | --- |
| `clean-starter` | none | supplied baseline |
| `attack-starter` | bounded sensor offset | supplied baseline |
| `attack-student` | same attack plan | your `student_watchdog.py` |
| `clean-student` | none | your `student_watchdog.py` |

## Run one case, then the four-case comparison

Install and start Docker Desktop (or Docker Engine with Compose). From **this
folder** run:

```sh
./run.sh clean-starter
./run.sh all
```

The first build downloads and compiles Gazebo/ArduPilot components and may take
many minutes. On an Apple Silicon Mac, the currently pinned public SITL
binary requires `linux/amd64` emulation, which may be substantially slower;
the route is timed by simulator time, with a separate wall-time guard. The
container needs about 6 GB RAM and 4 CPUs. Each case starts with a fresh
simulator and flight-controller state. The Compose service exposes **no**
network port to the host.

Edit `attack.py` to change the attack time, direction, or strength within its
limits. Edit `student_watchdog.py` to change what the Blue monitor requests.
Both are mounted from the host, so your next `./run.sh` invocation uses your
edits. The supplied starter reacts to an abrupt location jump, then resumes
AUTO after a short quiet interval. A smooth spoof or a persistent offset can
defeat that assumption; students should examine both missed attacks and false
stops. `starter_watchdog.py` is the original comparison and should stay as-is.

Each case writes three files into `runs/`: a JSON summary, timestamped JSONL
events, and an offline SVG route plot. The plot distinguishes the **assigned
route** (gray), **Gazebo simulator truth** (blue), and **GPS reported to the
controller** (red). It is generated from telemetry and is not a live camera
view. Check `mission_completed`, `airborne_observed`, controller mode events,
GPS parameter confirmations, and route deviation. An accepted parameter by
itself does not prove a changed physical trajectory or a successful defense.

To test basic code without starting a flight (after the image has built):

```sh
docker compose config --quiet
docker compose build sim
docker compose run --rm --no-deps sim python3 -m unittest -v test_logic.py
```

## How this differs from the CTF

This is an **analogous practice flight** over a generic Gazebo runway, not the
CTF2 stadium mission. The CTF's private GPS edit API and arbiter are not
reimplemented or claimed here. The simulator-parameter attack can produce a
different onset and controller response from the CTF attack. Students can
practice the same reasoning pattern—observe, alter a sensor input, revise a
watchdog, and compare four controlled flights—but cannot use these receipts
as evidence that the CTF mission was run or defended.

## Public source and pinned versions

- [ArduPilot Copter 4.7.3 SITL executable](https://firmware.ardupilot.org/Copter/stable-4.7.3/SITL_x86_64_linux_gnu/arducopter),
  official versioned download, SHA-256
  `0cab7ddc9e9f1ef7f7c88138fcf925824fb952eb15e4f69cd6c8ef9210e25bf0`.
  Its corresponding [ArduPilot source revision](https://github.com/ArduPilot/ardupilot/tree/d9c5097c3d8333435712ffed86bca8ce00c4bb46)
  is `d9c5097c3d8333435712ffed86bca8ce00c4bb46`. ArduPilot is GPLv3;
  the course repository downloads the official binary at build time rather
  than checking it into Git.
- [Official ArduPilot Gazebo plugin](https://github.com/ArduPilot/ardupilot_gazebo/tree/f116b03552d05c8d0b0bed5ed67033a1183121d1),
  revision `f116b03552d05c8d0b0bed5ed67033a1183121d1`, LGPLv3.
  The Dockerfile builds it from that revision, with Gazebo Harmonic from
  [OSRF's Ubuntu packages](https://gazebosim.org/docs/harmonic/install_ubuntu/).
- [pymavlink](https://github.com/ArduPilot/pymavlink), pinned to PyPI
  version `2.4.50`, is used for MAVLink mission upload and telemetry.
- The Iris parameter file comes from the official ArduPilot Gazebo frame
  [source revision](https://github.com/ArduPilot/ardupilot/blob/5966b6674efe2a3ea1592b61719def875e70b87b/Tools/autotest/default_params/gazebo-iris.parm).
- The student attack plan, watchdog, runner, tests, route plot, and scripts in
  this folder are newly authored teaching code; no private CTF source was copied.

## Known test gate

The code and Compose file can pass static checks before class without touching
the live Docker VM. The **first actual flight** must still demonstrate: a
Gazebo-backed takeoff, AUTO waypoint progression, GPS parameter confirmation,
red/blue track separation for the attacked run, actual BRAKE/AUTO heartbeat
transitions if requested, and a clean, useful baseline. If any of those fail,
do not give this package to students as a runnable release.
