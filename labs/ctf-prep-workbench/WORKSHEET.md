# CTF Prep Workbench Worksheet

This worksheet supports individual reflection and collaborative class work.
It is not an official HW3 submission specification; use the published course
assignment for the final format and due date. There is no required fall-break
work in this activity plan.

## Part A: Observe

Before opening the controller or process views:

1. Draw the observed communication map. Label only what the packets establish;
   distinguish supplied asset-role labels from packet-derived facts.
2. Cite the packet number for the operation that may cause a physical effect.
   What are its Modbus function, direction, destination, register, and value?
3. What does the corresponding protocol response establish? List at least two
   physical or program facts it does **not** establish.
4. Predict two different physical outcomes consistent with the network-only
   evidence.

After opening the controller and process views:

5. Trace request → program decision → motor output → reported status → physical
   outcome → protection. Cite one fact from each source and revise your claim.
6. Which inputs are declared in the starting interlock but omitted from its
   start-permission decision? Why does that omission matter?

## Part B: Control

For the transfer-skid start request, propose one control at each distinct
boundary:

| Boundary | What would it observe or enforce? | What evidence proves it worked? |
|---|---|---|
| Network detection / segmentation | | |
| Controller prevention | | |
| Independent containment | | |
| Recovery / service verification | | |

Then compare the fixed replay cases. Record a **prohibited case** where the
discharge valve is closed and a **legitimate-service case** where it is open.
For each, state the controller decision, actual physical outcome, and whether
the safety and service properties hold. A deny-all rule does not satisfy the
legitimate-service requirement. An alert is not a block; a trip is not proof of
safe initial authorization.

State a bounded final claim and name the evidence that could falsify it.

## Part C: Challenge

Open the changed-assumption case. The last valve-open report is 30 seconds old
while the valve is now physically closed. Explain why a check of the last
reported value is insufficient. Revise the control with a freshness or
independent-state condition and identify a positive service test that should
still pass after the revision.

## Compact report outline

- System and authority map with evidence labels.
- One consequential command path and its packet reference.
- A control proposal or implementation, with prohibited and legitimate tests.
- One challenged assumption and a revised, bounded claim.
- What remains unknown or untested.
