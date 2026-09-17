# HW2 toolchain: what is real, and what each layer establishes

`analyze.sh` is a course-friendly launcher, not a C analyzer. Its raw results
come from Clang and Frama-C. Other wrappers start or query real PLC and
network tools in the prepared SPHERE realization. The local fallback is
explicitly a model; do not call its rows packets or OpenPLC execution.

| Question | Backend used in the prepared realization | Evidence | What it does *not* establish |
| --- | --- | --- | --- |
| What C paths exist? | [Clang Static Analyzer](https://clang.llvm.org/docs/analyzer/developer-docs/DebugChecks.html) `debug.DumpCFG` | `analysis/raw/clang_cfg.txt`, projected DOT/SVG | Which path ran, or whether a physical attack succeeds |
| What may influence the valve? | [Frama-C Eva](https://www.frama-c.com/fc-plugins/eva.html) with `-deps` | `analysis/raw/framac_dependencies.txt`, normalized JSON | Exact taint through Modbus or behavior outside the harness |
| Does the IEC program compile and run? | Pinned OpenPLC v3 Runtime image, its own `compile_program.sh`, and actual controller scan | ST source, runtime logs, coil responses | Universal correctness or equivalence to every C path |
| What crossed the wire? | PyModbus 3.8.6, tcpdump, [TShark](https://www.wireshark.org/docs/man-pages/tshark.html) | `network.pcap`, TShark-derived `modbus_trace.csv` | Ground-truth tank level |
| What happened to the process? | Disclosed Python tank model and property checker | `process.csv`, oracle verdict | A claim about a physical tank |
| Which settings fail in a bounded search? | Disclosed course candidate generator → executor → property checker | Search table and counterexample bundle | Exhaustive proof or a generic coverage-guided fuzzer |

## Static analysis provenance

The deployed node provisions Clang 14 from Ubuntu and the official Frama-C
33.0 (Arsenic) Linux bundle, identified by SHA-256
`c754c31bb32d151acf7db3bcfdc5181b076bdbff813b19049e984f639eba3735`.
Graphviz renders Clang's basic-block graph; Python only translates Clang's
block labels and successor IDs to DOT. Clang's output is saved unchanged.

Frama-C analyzes `controller.c` through
`representations/framac_harness.c`. The harness initializes the prior valve
state to either Boolean value and supplies a reported level between 0% and
100%. Frama-C's own dependency report says whether the state depends on the
reported level and whether it may depend on `SELF` (its previous value).
`static_view.py` parses that report; it does not infer C semantics. The
exact harness used for each run is saved as `runs/analysis/raw/framac_harness.c`.
generated `runs/analysis/TOOLCHAIN.md` records the exact commands, versions,
source hash, and limitations of *that* invocation. If Frama-C is unavailable
on a local fallback machine, the dependency claim is marked unavailable. In
the prepared realization it is required.

The name mapping from C variables to PLC/Modbus concepts comes from
`representations/controller_contract.json`, not from either analyzer.
Frama-C reports possible dependencies under an abstract input range; it
does not prove exploitability or absence of behavior outside that range.

## PLC and network provenance

The image is pinned to OpenPLC v3 commit
`b5d41356dab4aeadca0dd7ca64ba542f870b595d` (container digest is pinned
in staff provisioning). Its entrypoint mounts the released ST and invokes
that revision's `webserver/scripts/compile_program.sh` before starting the
runtime. This is an actual ST compilation and PLC scan, not the C reference
model. PyModbus writes the reported REAL to the fixed Modbus registers and
reads the fixed coil. tcpdump captures the isolated interface; TShark
decodes the pcap. `modbus_trace.csv` is a projection of those packets.
`TOOLCHAIN.json` in each live bundle records the exact tcpdump/TShark
versions and commands, PyModbus version, pinned OpenPLC source commit, and
the pcap-to-table relationship; the evidence manifest covers that file.
`network_trace.csv` in the local fallback is only modeled semantic evidence.

## Optional next tools, not hidden requirements

- [CBMC](https://www.cprover.org/cbmc/) can check bounded C assertions and
  produce counterexamples. It is not part of the required run or a claim of
  C↔ST equivalence here.
- [IEC Checker](https://github.com/iec-checker/iec-checker) can provide separate
  static findings on IEC source. It is not the OpenPLC compiler used in this
  realization.
- [RTAMT](https://github.com/nickovic/rtamt) can express richer temporal
  properties; the required 90% monitor remains transparent Python.
- [Zeek's Modbus analyzer](https://docs.zeek.org/en/current/scripts/base/protocols/modbus/main.zeek.html)
  and [Suricata's Modbus support](https://docs.suricata.io/en/suricata-8.0.4/rules/modbus-keyword.html)
  are future network-monitoring directions, not sources of the HW2 packet
  table. Binary CFG recovery with [angr](https://docs.angr.io/en/latest/analyses/cfg.html)
  is another optional comparison to the source-level Clang graph.
