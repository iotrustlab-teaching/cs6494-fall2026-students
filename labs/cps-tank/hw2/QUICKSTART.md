# HW2 quick start

This lab follows one question through program, PLC, network, controller, and process views: **how can an observation influence an actuator, and does the simulated tank remain below its 90% high-high limit?**

## Start

Use the **process-node shell** reached through your assigned SPHERE XDC (not
the XDC shell itself). Follow the course-provided access instructions; do not
guess a host or use another team's realization. On the process node, prepare
your workspace, change into the printed HW2 directory, and run:

```bash
hw2-prepare
cd ~/cs6494-hw2/hw2
./preflight.sh --require-sphere
./analyze.sh
./run_nominal.sh
./run_spoof.sh
```

For an **instructor-authorized** local fallback, clone the public starter
repository on your own machine, enter this directory, and omit
`--require-sphere`:

```bash
git clone https://github.com/iotrustlab-teaching/cs6494-fall2026-students.git
cd cs6494-fall2026-students/labs/cps-tank/hw2
./preflight.sh
./analyze.sh
./run_nominal.sh
./run_spoof.sh
```

Each run prints the path to a new evidence directory and refuses to overwrite
an existing one. The prepared process node sets `HW2_TRANSPORT=modbus_tcp`, so
the short run commands use real OpenPLC and captured Modbus TCP. The authorized
local fallback uses modeled JSON/TCP semantics and produces no packet capture.
On a local machine without Frama-C, `./analyze.sh` still produces Clang's CFG
but explicitly marks the dependency result unavailable; the prepared SPHERE
node requires both analyzers. See [the toolchain map](TOOLCHAIN.md).
SPHERE dependencies should already be installed; report a failed preflight
line to staff rather than installing or discovering infrastructure yourself.

## Check the evidence

Replace `RUN_DIRECTORY` with the printed path:

```bash
./show_evidence.sh RUN_DIRECTORY
```

In the prepared SPHERE path, also run `./show_network.sh RUN_DIRECTORY` to
decode the real pcap. It requires `network.pcap` and `tshark` and is **not** a
local-fallback command.

Open these files first in either path:

1. `timeline.csv` — the compact observation → decision → command → process view.
2. `oracle_ladder.json` — layer-specific verdicts; its fields differ by transport.
3. `property_results.json` — the finite physical-property verdict and first violation.
4. `process.csv`, `observations.csv`, and `controller.csv` — source layers behind the joined timeline.

For a SPHERE run, additionally use `network.pcap` (traffic captured on the
process node's experiment-local interface) and `modbus_trace.csv` (a `tshark`
projection derived from that pcap). For the authorized local fallback, use
`network_trace.csv` and `messages.jsonl` only as **semantic reconstruction**;
neither is packet evidence.

Your work begins after the commands succeed: explain why the two cases differ, which evidence supports the property verdict, and what the run cannot establish.

## Bounded search

Choose and justify a small range, then run it. For example:

```bash
./search.sh --bias -20 -35 -50 --start 4 8 12
```

This is finite testing. Finding no counterexample would not prove safety.

## Program-plane observation

This is an instructor demonstration, not a required student command. Staff may
compare a baseline and known modified ST artifact through the bounded TSV-style
gate. The local demonstration does not contact or program a PLC. Modbus
process-data writes and program management are different planes.

## Reset

```bash
./reset.sh
```

In SPHERE, every run initializes a new process model and first writes 56% to
put the stateful OpenPLC inlet command in its CLOSED baseline. `./reset.sh`
repeats that fixed initialization, waits for a scan, verifies coil 0 is CLOSED,
and retains evidence. In the local fallback, every run starts fresh in memory;
reset removes only allowlisted transient scaffold files and retains evidence.

## Optional live view

The instructor may provide optional viewer URLs for a separate tank demo.
Those pages are not automatically connected to your HW2 realization; do not
use their screenshots as a substitute for your own evidence bundle.
