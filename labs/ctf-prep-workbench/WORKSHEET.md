# Utility OT Security Workbench Worksheet

This is a classroom exercise, not the official HW3 submission specification.
Use the course assignment for deadlines and required format. The browser can
support instructor/paired exploration, but the written reasoning below does
not depend on saved browser state or a live backend.

## Discover and Interpret

1. **Discover.** Before opening the site record, list the packet-observed IP
   and MAC endpoints. For each, separate a packet fact from an inferred type.
   What vendor, model, or process role remains unknown?
2. **Compare sources.** Open the site record. Which six rows are inventory
   leads but not observed assets? Which group labels are suggestions rather
   than your assignments? Distinguish packet-derived client/server direction
   from supplied names and process roles.
3. **Trace communication.** Draw the two observed client-to-controller paths. Cite packet
   numbers, directions, protocol, reads/writes, and one register of interest.
   Which site-record leads have no observed conduit here?
4. **Interpret.** Identify the consequential candidate using requester,
   operation, target, value, and response. Keep the specific Modbus fields too.
   What does packet #6 establish about packet #5, and what does it not prove?
   How would an exception response differ? Record an initial claim, a possible
   falsifier, a positive-service test, and one remaining unknown.

## Map, Govern, and Test

5. **Map.** Trace packet #5 → register 120 → illustrative Structured Text
   decision → modeled motor output → physical process replay. Label each link
   OBSERVED, SUPPLIED, AUTHORED, or UNVERIFIED. Cite reported-state packets
   #4, #8, and #10 separately from authored physical valve, motor, flow,
   pressure, and protection state. What evidence would verify the physical link?
6. **Assign and prioritize.** Explicitly assign groups to the observed
   endpoints and give a process criticality assessment. Explain where the
   site record helps and where it remains unverified; these are not Cisco
   product risk scores.
7. **Govern the network.** Choose a source group, destination group, operation,
   and policy action. Run the what-if simulation. Report what happens to
   packet #5 and the separate authored legitimate-service test. Does the rule
   preserve service? A network permit is not physical authorization, and this
   simulation is not a deployed switch/firewall rule.
8. **Place controls.** Give one network control and one state-aware controller
   control. Name a separate containment and recovery check. An alert does not
   prevent actuation; a trip does not prove safe initial authorization.
9. **Test both directions.** Use the prohibited and legitimate-service cases.
   For each, state the decision, physical outcome, safety property, and service
   result. A deny-all defense does not pass the positive service test.

## Assumption Stress Test and Revise

10. The last valve-open report is 30 seconds old while the valve is now
    physically closed. Which earlier assurance step no longer follows?
    State what must expire, be rechecked, or be independently verified.
11. Revise the earlier bounded claim. Name evidence that would falsify it, a
    positive service test that should still pass, and remaining uncertainty.

## Visibility comparison

| Cisco-style network visibility can establish | Additional CS 6494 evidence must establish |
|---|---|
| Observed endpoints and interfaces | Which device identity and process role are actually verified |
| Protocol, direction, operations, group conduits | Register meaning and controller decision |
| What a proposed network policy would match | Whether an allowed operation is safe in the current state |
| Network event or alert | Physical consequence, containment, restoration, and bounded assurance |

## Compact report

- Asset and authority map with observed / supplied / authored / unverified labels.
- One consequential command path with packet references and provenance per link.
- What the protocol response does and does not establish.
- Proposed group/segmentation rule and its effect on the prohibited and
  legitimate-service cases.
- Controller/process guardrail and the state it requires.
- Changed assumption and revised bounded claim.
- Remaining uncertainty or untested operation.
