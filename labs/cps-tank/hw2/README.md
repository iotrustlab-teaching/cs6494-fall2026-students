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

## Part A — Read the program (35–45 minutes)

**Scaffolded mechanics.** Run `./analyze.sh`. Inspect
`representations/controller.c`, the generated CFG, and the dependency map.

**Student decision.** Identify the untrusted observation, the two comparisons,
the state that survives between scans, and the final actuator decision. Trace
one feasible path that keeps the inlet open.

**Student artifact.** An annotated dependency chain or a short CFG explanation
that names the input, retained state, decision, and output.

**Learning outcome.** Distinguish what static structure says *can* happen from
what a later execution says *did* happen.

**CTF1 transfer.** Read an unfamiliar controller and locate the leverage point
without being handed the answer.

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
process/data plane or the engineering/program-management plane.

**Student artifact.** A completed concept/tag/address/owner/authority table and
a two- or three-sentence explanation of why a Modbus data write is not a PLC
program download.

**Learning outcome.** Connect source intent, PLC memory, and network-visible
objects without treating representations as interchangeable proof.

**CTF1 transfer.** Discover observation and action surfaces, then bound what
each capability actually permits.

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
to controller input, branch, inlet command, and true process effect.

**Student artifact.** Your before-run prediction, the observed divergence or
confirmation, and a causal explanation citing specific timestamps/rows.

**Learning outcome.** Distinguish an accepted operation from controller
response and physical consequence; each requires separate evidence.

**CTF1 transfer.** Act inside a bounded environment and determine what actually
happened across layers.

## Part D — Search and define failure (45–60 minutes)

**Scaffolded mechanics.** Choose one dimension—initial level, manipulation
start, or sensor bias—and run a small disclosed search. Example:

```bash
./search.sh --bias -20 -35 -50 --start 4 8 12
```

You are not implementing a fuzzer.

**Student decision.** Choose and justify a range and step size. Identify which
oracle layer answers the physical question and explain why runner completion,
controller responsiveness, or reported state alone can miss the failure.

**Student artifact.** A compact search table or plot plus the explored space,
oracle, any counterexample, and one sentence explaining why no observed
counterexample would not prove safety.

**Learning outcome.** Use systematic finite testing to look beyond one
execution while keeping the claim bounded.

**CTF1 transfer.** Replace random poking with a deliberate investigation
strategy.

## Part E — Evidence-backed conclusion (30–45 minutes)

**Scaffolded mechanics.** Use `network.pcap`, its derived
`modbus_trace.csv`, `timeline.csv`, `oracle_ladder.json`, and
`property_results.json`. Consult source-layer files only when your claim needs
them. The pcap establishes interface traversal and a Modbus operation, not the
controller branch, actuator response, or physical consequence by itself.

**Student decision.** Select the minimum evidence needed to support your
physical-property claim.

**Student artifact.** A concise investigation memo containing:

1. what happened;
2. the relevant CPS property and verdict;
3. a causal explanation;
4. the minimum supporting evidence;
5. the strongest bounded claim you can defend; and
6. one stronger claim the experiment does not support.

**Learning outcome.** Match evidence to claims and disclose assumptions and
limits.

**CTF1 transfer.** Produce an evidence-backed postmortem rather than merely
reporting success or failure.

## Finish and recover

```bash
./reset.sh
```

Confirm your evidence still exists, download the required bundle/memo, and
stop or release your assigned realization using the course-provided control.

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
