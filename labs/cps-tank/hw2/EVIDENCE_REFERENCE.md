# HW2 evidence-field reference

The process, observation, controller, action, and joined timeline CSVs share
`elapsed_s`, the runner's simulation clock. The pcap-derived
`modbus_trace.csv` instead uses `time_s` relative to the packet capture; do
not equate those timestamps without aligning the run events.

| Artifact | Important fields | What it establishes | What it does not establish |
|---|---|---|---|
| `metadata.json` | case, model, parameters, schema, layers | Declared run configuration and provenance | That the named source was untampered |
| `process.csv` | `true_level_pct`, `physical_state`, rates | State calculated by the software process model | A real tank's state |
| `observations.csv` | reported level, controller input, source, attack flag | The observation delivered inside this model | How a real sensor became compromised |
| `controller.csv` | input, command, decision | The controller's input/output relation per step | That a physical actuator obeyed |
| `actions.csv` | actuator, command, reason | Valve command transitions | Physical actuation outside the simulator |
| `timeline.csv` | truth, report, decision, command, states | Compact joined view on the common clock | A new independent evidence source |
| `network.pcap` | Ethernet/IP/TCP/MBAP and Modbus payloads | Traffic crossed the captured experiment interface | Which ST branch ran, whether an actuator obeyed, physical truth, or a program download |
| `modbus_trace.csv` | time, endpoints, transaction, function, address, raw and decoded value, provenance | Readable tshark projection derived from `network.pcap` | An evidence source independent of the pcap or physical causality |
| `requested_modbus_operations.csv` | requested fixed client operations and engineering values | Application-side intent and correlation aid | That a request traversed an interface or was accepted |
| `network_trace.csv` | plane, endpoints, function, operation, address, value, authority | Fallback-only semantic reconstruction of expected operations | That packets crossed a real interface or that a program was downloaded |
| `messages.jsonl` | direction, semantic payload | Model-generated application messages | Packets on a real network |
| `events.log` | perturbation, command, violation timing | Event ordering on the common clock | Causality by itself |
| `property_results.json` | expression, verdict, maximum, first violation | Result of one predicate over this finite trace | Universal safety or causal attribution |
| `oracle_ladder.json` | layer verdicts, whole-run reported maximum, and first-violation onset decision | Values needed to compare controller awareness at onset with the whole-run report | The interpretation of any disagreement, correctness outside this run, or causal attribution |
| `manifest.sha256` | digest and filename | Whether bundle files later changed | Who created them or whether the source was truthful |

## Default property

```text
P1: always(true_level_pct < 90)
```

The primary property and checker are provided. Your task is to justify the
chosen trace field, compare it with at least one plausible alternative field,
and interpret the result from your own run. In particular, inspect the
whole-run reported-state verdict and `physical_violation_onset_detection`
rather than assuming that agreement or disagreement has a fixed meaning. Then
either critique one limitation of the checker or define one small secondary
property. You are not being asked to invent a complete specification from
scratch.

## Evidence and claim layers

Keep the required claim layers distinct in your memo. Complete this worksheet
with evidence from your own run; a single file may support more than one claim,
but you must explain what it establishes at each layer.

| Claim layer | Exact evidence cited | What that evidence establishes | One limitation or stronger unsupported claim |
|---|---|---|---|
| Program-level capability |  |  |  |
| Runtime observation |  |  |  |
| Network/authority evidence |  |  |  |
| Physical/process evidence |  |  |  |
| Property verdict |  |  |  |

The primary SPHERE path combines a real OpenPLC runtime and captured Modbus
traffic with an emulated deployment and a simulated water-tank process. The
local fallback uses modeled JSON/TCP semantics instead. State explicitly which
path you used. Choose and defend one concrete claim that would require higher
fidelity rather than repeating this architecture description.

## Packet evidence

In the primary SPHERE path, `network.pcap` is core evidence and
`modbus_trace.csv` is derived from it with tshark. In the local JSON/TCP
fallback, `network_trace.csv` remains a semantic reconstruction and is labeled
as such. A packet trace establishes what crossed the captured interface; it
still cannot establish program semantics, physical truth, or the attack's
origin by itself.

Program-management evidence is separate again: an upload log and before/after
hash can establish that a controller artifact changed, but not that Modbus
process I/O performed the change or that the new behavior became unsafe.
