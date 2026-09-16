# HW2 grading rubric

Total: 100 points. Grade the reasoning and evidence, not command memorization.

| Area | Points | Full-credit evidence |
|---|---:|---|
| A. Program structure | 15 | Correct observation, strict branches, retained state, actuator output, and one feasible path |
| B. PLC/tag/network mapping | 20 | Correct concept-to-ST-to-address map, owner/authority labels, and data-plane/program-plane distinction |
| C. Prediction and causal execution | 20 | Prediction precedes run; explanation follows operation → input → branch → command → process |
| D. Bounded search and oracle | 20 | Justified finite space, correct oracle layer, counterexample interpretation, and no-proof limitation |
| E. Evidence-backed claim | 20 | Minimum relevant evidence, correct bounded claim, assumptions, and one explicitly unsupported stronger claim |
| Recovery and scope discipline | 5 | Reset/release confirmed; no out-of-bounds target or unsupported evidence claim |

## Performance anchors

- **Excellent (90–100):** cross-layer reasoning is precise; each claim is
  matched to evidence and limitations.
- **Competent (75–89):** main causal chain and property are correct; small
  mapping or evidence-boundary errors do not alter the conclusion.
- **Developing (60–74):** execution completed but reasoning collapses reported
  state into process truth, or treats an accepted write as physical proof.
- **Insufficient (<60):** mostly command output, an unbounded safety claim, or
  no defensible causal/evidence chain.

## Safety and integrity handling

Do not reward probing outside the assigned realization, arbitrary address
entry, credential sharing, or program upload. Route suspected boundary
violations to course policy rather than improvising a technical penalty.

## Evidence checks used during grading

- A pcap establishes traffic on the captured interface; it does not establish
  PLC semantics, actuator obedience, or process truth.
- Primary SPHERE `modbus_trace.csv` is a readable projection of
  `network.pcap`; fallback `network_trace.csv` is only modeled semantics and is
  not a packet capture.
- A property `FAIL` exit is a valid experiment result, not a broken tool.
- A finite `PASS` is not proof of universal safety.
- Alternative evidence selections earn full credit when the student explains
  why they are sufficient and what they cannot establish.
