# HW2 — From Controller Logic to CPS Evidence

> **Student release.** Canvas is authoritative for the due date, submission
> mechanism, and any announced adjustments.

## Purpose

You will follow one causal chain across several views of the same small water
tank:

```text
reported level -> controller branch -> inlet command -> true tank level
```

The goal is not to master OpenPLC, packet tools, or fuzzing. The goal is to
inspect unfamiliar control logic, predict its behavior, exercise a bounded
course system, choose the right oracle, and support a limited claim with the
minimum appropriate evidence.

Expected work time: **3.5–4.5 hours** after the prepared environment passes
preflight.

## Authorization and safety boundary

Use only your assigned course realization and the fixed commands in this
assignment. The prepared manipulation can affect only the reported-level object
in your own realization, for a bounded interval. Do not enter arbitrary hosts,
ports, tags, addresses, credentials, or programs. Do not probe other course
instances. Run `./reset.sh` when directed and release the realization using
the course instructions.

## Start

```bash
./preflight.sh
```

The prepared SPHERE path must identify your instance, team, and expiry. If it
does not, stop and send the failed line to course staff. Do not install
packages. The instructor may authorize the identical local fallback if SPHERE
is unavailable. In SPHERE, the same short commands select the real
OpenPLC/Modbus path automatically; the local fallback is explicitly labeled
as the JSON/TCP regression path.

**Deeper dive (optional).** `preflight.sh` is a small wrapper around
`preflight.py`. The base check verifies Python, the released files, and a
writable evidence directory. In a prepared realization,
`./preflight.sh --require-sphere` additionally checks the course identity and
expiry variables, `pymodbus`, `tcpdump`, `tshark`, the fixed packet-capture
privilege, and reachability of the fixed OpenPLC Modbus endpoint. It does not
install software, start services, or change the controller. Run
`./preflight.sh --help` to inspect its one optional flag.

## Part A — Read the program (35–45 minutes)

**Scaffolded mechanics.** Run `./analyze.sh`. Inspect
`representations/controller.c`, the generated CFG, and the dependency map.

**Student decision.** Identify the untrusted observation, the two comparisons,
the state that survives between scans, and the final actuator decision. Trace
one feasible path that keeps the inlet open. Then list two or three assumptions
that must hold for this software influence to produce the physical property
violation, and name one reason the dependency could exist while the physical
violation remains unreachable.

**Student artifact.** An annotated dependency chain or a short CFG explanation
that names the input, retained state, decision, and output, followed by your
physical-realizability assumptions and one reachability limitation.

**Learning outcome.** Distinguish what static structure says *can* happen from
what a later execution says *did* happen.

**CTF1 transfer.** Read an unfamiliar controller and locate the leverage point
without being handed the answer.

**Deeper dive (optional).** `analyze.sh` forwards its arguments to
`static_view.py`. That script reads `representations/controller.c`, checks for
the expected controller symbols, and writes `controller_cfg.dot` plus
`dependency_map.json`. Use `./analyze.sh --out runs/my-analysis` to choose a
fresh output directory, then inspect the DOT edges and JSON fields. This is a
transparent teaching extractor, not a general-purpose C analyzer, but the
control-flow and data-dependency questions it exposes are the same questions
asked by production static-analysis tools.

## Part B — Map PLC logic and network authority (45–60 minutes)

**Scaffolded mechanics.** Inspect `representations/controller.st` and
`REPRESENTATION_MAP.md`. Map the reported REAL to `%MD0` / holding
registers 2048–2049 and the inlet BOOL to `%QX0.0` / coil 0. Inspect the
captured Modbus operations with:

```bash
./show_network.sh RUN_DIRECTORY
```

`modbus_trace.csv` is generated from the run's real `network.pcap`; it is not
a parallel modeled record.

**Student decision.** For each provided operation, decide who owns it, who can
observe it, whether it is a read or write, and whether it belongs to the
process/data plane or the engineering/program-management plane. Explain why a
syntactically valid or accepted write does not by itself establish that the
writer was authorized, that the controller used the value, or that the result
was safe.

**Student artifact.** A completed concept/tag/address/owner/authority table and
a two- or three-sentence explanation of why a Modbus data write is not a PLC
program download. Include one example separating protocol validity from
authorized or safe outcome.

**Learning outcome.** Connect source intent, PLC memory, and network-visible
objects without treating representations as interchangeable proof.

**CTF1 transfer.** Discover observation and action surfaces, then bound what
each capability actually permits.

**Deeper dive (optional).** `show_network.sh` calls `show_network.py`, which
invokes the real `tshark` CLI on the saved `network.pcap`, selects Modbus
packets, correlates requests and responses by transaction ID, and decodes the
two 16-bit `%MD0` words as one IEEE-754 REAL. Inspect `FIELDS`, `OPERATIONS`,
and `decode_real` in that script. On your own saved capture, you may try a
read-only display filter such as
`tshark -r RUN_DIRECTORY/network.pcap -Y 'modbus.func_code == 16'`. Change
display fields or filters, not capture targets, hosts, addresses, or live
traffic outside your assigned realization.

## Part C — Predict, then execute (45–60 minutes)

**Scaffolded mechanics.** Before executing, write a prediction for the nominal
case and for the prepared reported-level manipulation. Then run:

```bash
./run_nominal.sh
./run_spoof.sh
./show_evidence.sh RUN_DIRECTORY
./show_network.sh RUN_DIRECTORY
```

Use your own printed run directories. In the prepared SPHERE realization, the
authorized manipulation is fixed to the allowlisted reported-level seam and is
automatically bounded and logged.

**Student decision.** Identify where observed behavior first diverges from your
prediction, or state that it agrees. Follow the full chain: network operation
to controller input, branch, inlet command, and true process effect. Before the
run, name the evidence that would distinguish your nominal and manipulated
predictions.

**Student artifact.** Your before-run prediction, the observed divergence or
confirmation, and a causal explanation citing specific timestamps/rows.

**Learning outcome.** Distinguish an accepted operation from controller
response and physical consequence; each requires separate evidence.

**CTF1 transfer.** Act inside a bounded environment and determine what actually
happened across layers.

**Deeper dive (optional).** `run_nominal.sh` and `run_spoof.sh` are dispatch
wrappers. When `HW2_TRANSPORT=modbus_tcp`, they call
`modbus_tank_run.py`: each cycle writes the fixed reported-level register pair,
waits for the real OpenPLC scan, reads coil 0, advances the process model, and
records a pcap plus aligned evidence tables. Its endpoint, addresses, value
floor, and manipulation window are deliberately not command-line parameters.
The local fallback calls `hw2_lab.py`, where you can safely explore timing in a
fresh bundle, for example
`./run_case.sh sensor_spoof --duration 48 --tick 0.5 --out runs/spoof-48s`.
Compare the two runners to identify which layers are real tooling, emulated,
simulated, or reconstructed.

## Part D — Bounded search and oracle (45–60 minutes)

**Scaffolded mechanics.** Choose one dimension—initial level, manipulation
start, or sensor bias—and run a small disclosed search. Example:

```bash
./search.sh --bias -20 -35 -50 --start 4 8 12
```

You are not implementing a fuzzer. You are designing a bounded search over an
allowed input or perturbation surface.

**Student decision.** Choose and justify a range and step size, including why
the selected values could expose the property violation. Identify which oracle
layer answers the physical question and explain why runner completion,
controller responsiveness, or reported state alone can miss the failure. The
primary property and checker are provided: explain why they consume process
truth rather than reported state, then either critique one limitation of the
checker or define one small secondary property.

**Student artifact.** A compact search table or plot plus the explored space,
oracle, and your checker critique or secondary property. If you find a
violation, describe it as a concrete counterexample under the tested model,
starting state, input space, and horizon. If you do not, state the search bounds
and explicitly explain why the negative result does not prove safety.

**Learning outcome.** Use systematic finite testing to look beyond one
execution while keeping the claim bounded.

**CTF1 transfer.** Replace random poking with a deliberate investigation
strategy.

**Deeper dive (optional).** `search.sh` forwards to `search_cases.py`. The
script takes the Cartesian product of `--initial`, `--start`, and `--bias`,
constructs a fresh tank and retained controller state for every candidate, and
evaluates the process-truth property over a 36-second horizon. Try
`./search.sh --initial 45 55 --start 6 10 --bias -25 -40 --out runs/my-grid.csv`.
Read `evaluate()` to see the 5% reported-value floor, state update order, and
exact point at which the oracle is sampled. These are experiment parameters,
not arbitrary network targets.

## Part E — Evidence-backed conclusion (30–45 minutes)

**Scaffolded mechanics.** Use `network.pcap`, its derived
`modbus_trace.csv`, `timeline.csv`, `oracle_ladder.json`, and
`property_results.json`. Consult source-layer files only when your claim needs
them. The pcap establishes interface traversal and a Modbus operation, not the
controller branch, actuator response, or physical consequence by itself.

**Student decision.** Select the minimum evidence needed to support each layer
of your conclusion. Keep program-level capability, runtime observation,
network/authority evidence, physical/process evidence, and the property verdict
separate rather than treating one layer as proof of another.

**Student artifact.** A concise investigation memo containing:

1. what the program structure shows is possible;
2. what actually executed at runtime;
3. what the network/authority evidence shows was read or written, and by whom;
4. what the simulated physical process did;
5. the relevant CPS property, its verdict, and why the chosen oracle supports it;
6. the minimum evidence supporting each claim layer;
7. the strongest bounded claim you can defend and one stronger unsupported claim;
8. which parts of the experiment are real, emulated, or simulated, and one claim
   that would require higher fidelity than this lab provides.

**Learning outcome.** Match evidence to claims and disclose assumptions and
limits.

**CTF1 transfer.** Produce an evidence-backed postmortem rather than merely
reporting success or failure.

**Deeper dive (optional).** `show_evidence.sh` runs
`evidence_summary.py`, which first validates the bundle and then selects the
smallest fields needed for its printed claims. `collect.sh` independently
checks required files, columns, schema version, pcap presence, cross-file
verdict agreement, and the SHA-256 manifest. The inspectable oracle in
`property_oracle.py` evaluates `always(true_level_pct < 90)` over
`process.csv`. For a non-destructive sensitivity check, try
`python3 property_oracle.py RUN_DIRECTORY --max-level 85 --no-write`; keep the
required 90% verdict unchanged and label the alternate threshold separately.

## Optional bonus exploration — OpenPLC Editor

This exploration is optional and carries no penalty if skipped. OpenPLC Editor
is a programming environment; the OpenPLC Runtime used in the required lab is
the component that compiles and executes the located ST.

1. Install or open OpenPLC Editor v3 on your own computer.
2. Choose **Open Project** and select the entire
   `representations/openplc_editor_project` folder (not an individual file).
3. Expand the `HW2TankController` program and compare its variable interface
   and ST body with `representations/controller.st`.
4. Find the retained `inlet_valve_open` state, both threshold comparisons, and
   the branch that leaves the previous command unchanged.

As you explore, consider: What is easier to understand in the Editor than in
the C/CFG view? What still requires runtime or process evidence? The prepared
PLCopen XML intentionally supports visual inspection only: the current
translation does not retain the ST `AT` locations. Therefore it cannot replace
`controller.st` in the live Docker/OpenPLC path and is not evidence that the
program was deployed or executed.

**Deeper dive (optional).** The project folder contains `plc.xml`, the
PLCopen interchange representation that the Editor renders, and
`beremiz.xml`, the small project descriptor. The required runtime instead
mounts the located `controller.st`; OpenPLC's runtime toolchain compiles that ST
and generates the I/O glue used by the process connection. Edit only a copy of
the Editor project and compare its exported logic with the original rather
than substituting it into the live lab.

## Finish and recover

```bash
./reset.sh
```

Confirm your evidence still exists, download the required bundle/memo, and
stop or release your assigned realization using the course-provided control.

**Deeper dive (optional).** `reset.sh` also dispatches by transport. The local
path removes only an allowlist of transient scaffold files and refuses an
unexpected runtime directory; it retains evidence bundles. The Modbus path
reconnects to the fixed controller, writes a disclosed 56% initialization
value, waits for a scan, and confirms coil 0 is CLOSED. This makes the retained
hysteresis state explicit rather than assuming that a new command or page load
reset the PLC.

## Instructor demonstration — not required student work

The instructor may compare baseline and modified teaching ST through a
TSV-lite bounded safety gate, then show a supported program deployment and
restore in an isolated environment. The exact interpretation is:

> TSV-lite asks the same architectural question: should a candidate controller
> pass a bounded safety check before deployment?

`ACCEPT` means only that no violation was observed in the disclosed finite
scenarios and assumptions. It is not formal proof, model checking, or the
original TSV implementation. Program hash change, behavior change, and unsafe
physical consequence remain three different claims.

## Submission

- Parts A–D responses;
- Part E investigation memo;
- the requested nominal/manipulated evidence identifiers or bundles;
- search results; and
- confirmation that reset/release completed.
