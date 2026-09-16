# What the HW2 tools do for you

`setup.sh` checks Python and the prepared C compiler, then runs existing and revision self-tests. The core experiment itself still uses only Python's standard library.

`analyze.sh` emits a small CFG and dependency map from the C teaching artifact. It exposes structure; you must interpret the observation-to-actuator path.

`verify_representations.sh` executes six stateful sequences through the reference, existing Python controller, compiled C, and supported ST model. Passing establishes bounded agreement on those sequences, not universal equivalence.

`run_nominal.sh` creates a fresh tank and controller, executes the unperturbed loop, records five evidence layers on one elapsed-time clock, and evaluates the provided example property.

`run_case.sh sensor_spoof` runs the same loop but, at 8 seconds, models an allowlisted inline network replacement of the observation sent to the controller. The physical model continues independently. The prepared value is `max(5%, true level − 50%)`; it does not directly set the valve, tank level, or PLC program.

`search.sh` runs a transparent finite grid over selected initial levels, attack starts, and sensor biases. It is bounded search, not a production fuzzer or proof engine.

`program_plane_demo.sh` compares hashes and bounded safety results for known baseline and modified ST files. It is offline and opens no network connection.

`collect.sh` checks required files, columns, schema version, and checksums. Passing validation means the bundle is structurally complete and unchanged since capture—not that its scientific interpretation is correct.

`property_oracle.py` evaluates `always(true_level_pct < 90)` over the finite process trace. It is deliberately ordinary Python so you can inspect and adapt the predicate. A passing finite run is not proof of universal safety.

`reset.sh` clears only known transient scaffold state. Every execution constructs a fresh model, so prior controller and tank state cannot leak into the next case. Evidence is retained.

The scripts intentionally automate setup, execution, timestamps, packaging, and basic validation. They do not answer why the property matters, whether the evidence is sufficient for your claim, what caused a violation, whether modeled network rows were real packets, or what stronger claim remains unsupported.
