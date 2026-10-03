# Utility OT Security Workbench Worksheet

This is a classroom exercise, not the official HW3 submission specification.
Use the course assignment for deadlines and required format. Collaborative
class investigation and individual written conclusions can coexist; there is
no required fall-break work in this activity plan.

## Monday: Discover → Group → Interpret

1. **Discover.** Before opening the site record, list the packet-observed IP
   and MAC endpoints. For each, separate a packet fact from an inferred type.
   What vendor, model, or process role remains unknown?
2. **Group.** Open the site record. Which six rows are inventory leads but not
   observed assets? Propose groups/zones for the three observed endpoints and
   explain why the site record is useful but not ground truth.
3. **Map.** Draw the two observed client-to-controller conduits. Cite packet
   numbers, directions, protocol, reads/writes, and one register of interest.
   Which site-record leads have no observed conduit here?
4. **Interpret.** Identify the candidate consequential request. What does its
   Modbus response establish? Give two different program or physical outcomes
   still consistent with network evidence alone.
5. **Prioritize.** Select one endpoint or conduit for deeper investigation.
   Record its evidence basis and an initial *process criticality* assessment;
   do not present this as a Cisco product risk score.

## Wednesday: Govern → Enrich → Test

6. **Govern the network.** Propose a group-to-group allow/deny rule and run
   the what-if simulation. Report what happens to packet #5 and to the
   separate authored legitimate-service test. Does the rule preserve service?
   Distinguish simulation from a deployed switch/firewall rule.
7. **Enrich.** In Assurance, trace packet #5 → register 120 → Structured Text
   decision → requested motor output → reported run state → physical flow and
   pressure → independent protection. Label which parts are packet-derived,
   supplied, or authored simulation.
8. **Place controls.** Give one network control and one state-aware controller
   control. Name a separate containment and recovery check. An alert does not
   prevent actuation; a trip does not prove safe initial authorization.
9. **Test both directions.** Use the prohibited and legitimate-service cases.
   For each, state the decision, physical outcome, safety property, and service
   result. A deny-all defense does not pass the positive service test.

## October 19: Challenge → Revise

10. The last valve-open report is 30 seconds old while the valve is now
    physically closed. Which earlier assurance step no longer follows?
    State what must expire, be rechecked, or be independently verified.
11. Revise a bounded claim. Name evidence that would falsify it and a
    positive service test that should still pass after your change.

## Visibility comparison

| Cisco-style network visibility can establish | Additional CS 6494 evidence must establish |
|---|---|
| Observed endpoints and interfaces | Which device identity and process role are actually verified |
| Protocol, direction, operations, group conduits | Register meaning and controller decision |
| What a proposed network policy would match | Whether an allowed operation is safe in the current state |
| Network event or alert | Physical consequence, containment, restoration, and bounded assurance |

## Compact report

- Asset and authority map with observed / supplied / inferred / unknown labels.
- One consequential command path with packet references.
- Proposed group/segmentation rule and its effect on the prohibited and
  legitimate-service cases.
- Controller/process guardrail and the state it requires.
- Changed assumption and revised bounded claim.
- Remaining uncertainty or untested operation.
