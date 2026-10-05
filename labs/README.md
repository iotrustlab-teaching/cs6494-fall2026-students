# Labs

Instructions and starter material for the scaffolded labs.

| Lab | Week | Status |
|---|---|---|
| [CPS Tank micro-lab](cps-tank/) | 3 | **available** |
| [HW2 — From Controller Logic to CPS Evidence](cps-tank/hw2/) | 4 | **available** |
| Agent-guardrail exercise | 6 | not yet published |
| [HW3 working sheet — From Requirement to Defensible Guardrail](substation-recovery-demo/HW3_WORKING_SHEET.md) | 7 | guided class activity; Canvas has submission settings |
| Reproducible SITL lab | 10 | not yet published |
| Integrity analysis | 11 | not yet published |

Each lab folder contains its instructions, any starter code or data, and what to submit. Submit
through Canvas unless the lab says otherwise.

## Lecture demos

- [Utility OT Security Workbench](ctf-prep-workbench/) — an optional offline fictional
  utility investigation with asset inventory, observed communication maps,
  group-policy what-if tests, and controller/process assurance. It is not the
  HW3 dependency; course announcements provide requirements and dates.
- [SMT solver demo](smt-solver-demo/) — the tank sensor-bias query, a bounded
  distribution-feeder example, and the mapping from executable controller code
  to Z3 constraints.
- [Live agent authority demo](agent-authority-demo/) — a local model proposes a
  fixed fake CPS action, while a deterministic policy gate decides whether the
  in-memory effect is allowed and records the evidence. Replay mode requires no model.
- [Substation Recovery Lab](substation-recovery-demo/) — the coached technical
  core of HW3, connecting a Structured Text repair to controller decisions,
  actual breaker positions, electrical consequences, protection, required
  service, and an individual bounded claim.
