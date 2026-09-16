# What the HW2 tools do for you

`preflight.sh` checks Python and released files. In the prepared SPHERE process
node, `./preflight.sh --require-sphere` also checks the supplied identity,
transport, fixed OpenPLC endpoint, and network tools. It reports the expiry
value but does not enforce the course resource deadline. Students do not need
to compile C or install dependencies.

`analyze.sh` emits a small CFG and dependency map from the C teaching artifact. It exposes structure; you must interpret the observation-to-actuator path.

`verify_representations.sh` executes six stateful sequences through the reference, existing Python controller, compiled C, and supported ST model. Passing establishes bounded agreement on those sequences, not universal equivalence.

`run_nominal.sh` selects the real OpenPLC/Modbus runner only when
`HW2_TRANSPORT=modbus_tcp`; otherwise it selects the labeled local model. Both
begin with a fresh tank model and evaluate the provided physical property.

`run_spoof.sh` uses the same transport selector for the bounded manipulation.
The reported value is `max(5%, true level − 50%)` during 8–16 seconds; it does
not directly set the valve, tank level, or PLC program. On SPHERE, the fixed
process client writes that value to OpenPLC with Modbus TCP and captures the
traffic. In the local fallback, `run_case.sh sensor_spoof` models the exchange
and produces no pcap.

`search.sh` runs a transparent finite grid over selected initial levels, attack starts, and sensor biases. It is bounded search, not a production fuzzer or proof engine.

`program_plane_demo.sh` compares hashes and bounded safety results for known baseline and modified ST files. It is offline and opens no network connection.

`collect.sh` checks required files, columns, schema version, and checksums;
for SPHERE bundles it additionally requires a nonempty pcap and consistent
derived Modbus trace. Passing validation means the bundle is structurally
complete and unchanged since collection—not that its scientific
interpretation is correct.

`property_oracle.py` evaluates `always(true_level_pct < 90)` over the finite process trace. It is deliberately ordinary Python so you can inspect and adapt the predicate. A passing finite run is not proof of universal safety.

`reset.sh` also selects by transport. The local path clears only known
transient scaffold state. The SPHERE path writes the fixed 56% initialization
value, waits for a real OpenPLC scan, and verifies that coil 0 is CLOSED so
retained hysteresis state cannot leak into the next run. Both retain evidence.

The scripts intentionally automate setup, execution, timestamps, packaging, and basic validation. They do not answer why the property matters, whether the evidence is sufficient for your claim, what caused a violation, whether modeled network rows were real packets, or what stronger claim remains unsupported.
