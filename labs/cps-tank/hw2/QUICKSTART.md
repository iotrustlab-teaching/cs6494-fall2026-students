# HW2 quick start

This lab follows one question through program, PLC, network, controller, and process views: **how can an observation influence an actuator, and does the simulated tank remain below its 90% high-high limit?**

## Start

In the prepared SPHERE XDC terminal:

```bash
./preflight.sh --require-sphere
./analyze.sh
./run_nominal.sh
./run_spoof.sh
```

For an instructor-authorized local fallback, run the same commands from this
directory but omit `--require-sphere`:

```bash
./preflight.sh
./analyze.sh
./run_nominal.sh
./run_spoof.sh
```

Each run prints the path to a new evidence directory. Nothing is overwritten.
The prepared SPHERE environment selects the OpenPLC/Modbus path automatically. For
an instructor-authorized local fallback, omit `--require-sphere`; that path is
the JSON/TCP regression system and must not be described as a packet capture.
You do not need to install packages or discover infrastructure.

## Check the evidence

Replace `RUN_DIRECTORY` with the printed path:

```bash
./show_evidence.sh RUN_DIRECTORY
./show_network.sh RUN_DIRECTORY
```

Open these files first:

1. `timeline.csv` — the compact observation → decision → command → process view.
2. `network.pcap` — packets captured on the process node's experiment-local interface.
3. `modbus_trace.csv` — a readable tshark projection derived from that pcap.
4. `oracle_ladder.json` — network, readback, reported-state, and physical-state verdicts.
5. `property_results.json` — the finite physical-property verdict and first violation.
6. `process.csv`, `observations.csv`, and `controller.csv` — authoritative source layers behind the joined timeline.

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

The model starts from a new in-memory state on every run. Reset removes only scaffold-owned transient files and deliberately retains evidence.

## Optional live view

The instructor may also provide viewer, operator, and attack URLs for the same tank model. Those pages help you see the loop, but screenshots are not a substitute for the submitted evidence bundle.
