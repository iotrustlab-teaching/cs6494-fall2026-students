# Substation Recovery Lab demo

This browser activity asks students to repair a Structured Text close interlock
without preventing legitimate service restoration. The one-line diagram,
breaker feedback, circuit measurements, protection response, mission checks,
and correlated event timeline come from a live backend simulation.

The activity is the coached technical core of **HW3: From Requirement to
Defensible Guardrail**. The individual submission is a compact evidence
portfolio, not a separate programming project. Use **HW3 submission** in the
top bar to enter a focused, full-page workflow. It presents the property,
counterexample, repair, tests, assumption stress test, and bounded claim one
checkpoint at a time. The builder saves locally, captures completed regression
metadata, checks evidence labels against the captured runs, and produces one
print-ready PDF for Canvas.
[HW3_WORKING_SHEET.md](HW3_WORKING_SHEET.md) is the non-browser fallback.

```text
browser request
  -> authenticated student workspace
  -> bounded command queue
  -> compiled Structured Text decision
  -> simulated breaker and electrical process
  -> independent protection and service checks
  -> correlated evidence timeline
```

The activity uses one small B0/S1/S2/S3 station throughout. Its five teaching
beats are described in [DEMO_SEQUENCE.md](DEMO_SEQUENCE.md):

1. identical zero-current readings can hide different topology;
2. the vulnerable controller permits an unsafe upstream close;
3. a target-only patch protects the wrong boundary;
4. a deny-all patch is safe but fails the service requirement;
5. a topology-aware repair preserves service and generalizes when the fault moves.

## Student use

For a hosted class session, open the URL supplied by course staff and enter your
assigned access code. Each code opens an isolated simulator, evidence stream,
controller source workspace, and OpenPLC runtime.

The hosted assignment is browser-only. Students do not clone this repository,
open a terminal, install Python or Node packages, run Docker, invoke a compiler,
or obtain a SPHERE shell. Compilation, OpenPLC execution, the electrical model,
regression tests, and evidence capture all run in the staff-managed SPHERE
environment. The browser keeps only the student's autosaved draft and the PDF
they explicitly save for Canvas.

The complete reference repair is hidden from the starting-source menu. Students
first commit to a repair and two tests; the instructor can then use the explicit
reference reveal for comparison. The repository still contains the reference
source for reproducibility, so this is a learning-sequence control rather than
a secrecy boundary.

Do not share access codes or use the exercise interface against any system other
than the assigned course environment.

The submission builder stores its draft in the current browser under the
authenticated student identity. It does not upload the report. Before leaving
the lab computer, choose **Create submission PDF**, use the browser's **Save as
PDF** destination, and submit `HW3_<uNID>.pdf` to Canvas. Canvas remains the
submission record.

If the hosted service is unavailable during an assigned work period, course
staff should pause or reschedule the activity. The local instructor fallback
below is not a student setup requirement.

## Local instructor fallback

The bundled local compiler is a macOS arm64 MatIEC build. On another platform,
set `MATIEC_IEC2C` to a compatible executable. Set `CC` if the system C compiler
is not available as `cc` or `clang`.

```bash
./run_demo.sh check
./run_demo.sh serve
```

Open `http://127.0.0.1:8765`. The first start creates a private preview code in
`runtime/access/student-invites.csv`. The entire `runtime/` directory is ignored
by Git and must never be committed.

The local fallback runs each validated ST function through MatIEC-generated C.
The hosted Linux mode runs the generated controller program in the pinned HW2
OpenPLC v3 image and exchanges requests and decisions over loopback-only Modbus.

## Commands

```text
./run_demo.sh serve           local MatIEC/native-function fallback
./run_demo.sh serve-openplc   Linux/Docker OpenPLC mode
./run_demo.sh check           unit and integration tests
./run_demo.sh rehearse        deterministic six-case evidence rehearsal
```

The rehearsal covers the vulnerable build, target-only patch, deny-all patch,
valid repair, legitimate restoration, moved-fault generalization, and compiler
error handling. It writes generated evidence under ignored `runtime/evidence/`.

## Execution boundaries

- The electrical process and breaker contacts are simulated teaching models.
- Student ST is actually compiled and executed; the UI does not decide whether
  a request is allowed.
- Position feedback is derived from simulated device state, not copied from the
  requested operation.
- Protection and service checks run independently of browser traffic.
- `OPEN` requires the separate human-recovery authority and an isolated branch.
- The hosted OpenPLC management interface and Modbus ports remain private.
- IEC-104 and live-agent request generation are not active. The interface labels
  this honestly rather than presenting HTTP or Modbus as IEC-104.

## Project layout

```text
static/               browser workspace
st/                   vulnerable, faulty, deny-all, and repaired ST variants
simulator.py          breaker, circuit, protection, tests, and event evidence
compiler.py           bounded local MatIEC compilation
openplc_*.py          pinned OpenPLC wrapper and Modbus decision handshake
access.py             private codes, sessions, and per-student workspaces
deploy/               staff-only Linux/SPHERE deployment packet
tests/                deterministic behavior, isolation, and runtime tests
```

MatIEC licensing and corresponding-source information are in `toolchain/`.
