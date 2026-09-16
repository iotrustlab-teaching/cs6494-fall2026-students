# HW2 evidence-field reference

All CSVs use `elapsed_s`, a deterministic simulation clock shared across layers.

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
| `oracle_ladder.json` | four verdicts and observed fields | Why software/report success can coexist with physical failure | Correctness outside this run |
| `manifest.sha256` | digest and filename | Whether bundle files later changed | Who created them or whether the source was truthful |

## Default property

```text
P1: always(true_level_pct < 90)
```

The checker uses process truth because the property concerns the simulated physical consequence. Checking only the reported sensor would answer a different question: whether the controller's *view* appeared below 90%.

The primary property and checker are provided. Your task is to explain why this
oracle is tied to process truth, interpret its finite-trace verdict, and either
critique one limitation or define one small secondary property. You are not
being asked to invent a complete specification from scratch.

## Evidence and claim layers

Keep these conclusions distinct in your memo:

| Claim layer | Typical support | Boundary |
|---|---|---|
| Program-level capability | source, CFG, dependency map | A feasible influence path may still be physically unrealizable |
| Runtime observation | controller/timeline events | Observed execution does not by itself identify network authority or physical truth |
| Network/authority evidence | pcap and derived Modbus trace | A valid or accepted operation is not proof of authorization, controller use, or safety |
| Physical/process evidence | simulator-owned process state | This establishes model behavior, not the state of a real tank |
| Property verdict | checker output over the named trace fields | A finite verdict is scoped to the tested model, inputs, initial state, and horizon |

The primary SPHERE path combines a real OpenPLC runtime and captured Modbus
traffic with an emulated deployment and a simulated water-tank process. The
local fallback uses modeled JSON/TCP semantics instead. State explicitly which
path you used and which claim would require higher fidelity, such as a hardware
actuator, physical tank, or a less constrained network/adversary model.

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
