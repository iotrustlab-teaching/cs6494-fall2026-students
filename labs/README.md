# Labs

Instructions and starter material for the scaffolded labs.

| Lab | Week | Status |
|---|---|---|
| [CPS Tank micro-lab](cps-tank/) | 3 | **available** |
| [HW2 — From Controller Logic to CPS Evidence](cps-tank/hw2/) | 4 | **available** |
| Agent-guardrail exercise | 6 | not yet published |
| Reproducible SITL lab | 10 | not yet published |
| Integrity analysis | 11 | not yet published |

Each lab folder contains its instructions, any starter code or data, and what to submit. Submit
through Canvas unless the lab says otherwise.

## Lecture demos

- [CTF Prep Workbench](ctf-prep-workbench/) — an offline OT visibility exercise
  with a frozen Modbus packet trace, controller/process context, and fixed
  guardrail cases. It is not the official HW3 assignment; course announcements
  provide submission requirements and dates.
- [SMT solver demo](smt-solver-demo/) — the tank sensor-bias query, a bounded
  distribution-feeder example, and the mapping from executable controller code
  to Z3 constraints.
- [Live agent authority demo](agent-authority-demo/) — a local model proposes a
  fixed fake CPS action, while a deterministic policy gate decides whether the
  in-memory effect is allowed and records the evidence. Replay mode requires no model.
- [Substation Recovery Lab](substation-recovery-demo/) — a browser-based
  Structured Text repair activity connecting controller decisions, actual
  breaker positions, electrical consequences, protection, and required service.
