# HW2 controller representation map

One stateful decision is shown in several representations because each view
answers a different question. They are not interchangeable evidence. This
reference supplies the mechanical name/address correspondence; the ownership,
authority, physical meaning, and controller-transition interpretation are part
of your analysis.

## Provided mechanical mapping

| Concept | C/Python view | IEC ST variable | OpenPLC location | Modbus object/address | Wire encoding |
|---|---|---|---|---|---|
| Reported observation | `reported_level_pct` / `reported_level` | `reported_level_pct` | `%MD0` | holding registers 2048–2049 | IEEE-754 binary32, big-endian bytes, high word first; one FC16 pair write |
| Low threshold | `LOW_LEVEL_PCT` / `LOW_LEVEL = 45` | `LOW_LEVEL_PCT` | internal | not transferred | n/a |
| High threshold | `HIGH_LEVEL_PCT` / `HIGH_LEVEL = 55` | `HIGH_LEVEL_PCT` | internal | not transferred | n/a |
| Prior command/state | `state.inlet_valve_open` / `controller.valve` | retained `inlet_valve_open` | `%QX0.0` | coil 0 | one Boolean bit |
| Actuator command | return from `controller_step` / `valve` | `inlet_valve_open` | `%QX0.0` | coil 0 | one Boolean bit |
| Process truth | `tank.level` in the Python process model | intentionally absent | none | not exposed as a PLC object | n/a |

## Student analysis worksheet

Complete this from the source and your own trace. Use a separate row when an
object has different owners or authorities at different layers.

| Concept/object | Owner | Who may observe it? | Read or write in the captured operation? | Process/data or engineering/program plane? | Physical meaning and evidence limit |
|---|---|---|---|---|---|
| Reported observation |  |  |  |  |  |
| Prior command/state |  |  |  |  |  |
| Actuator command |  |  |  |  |  |
| Process truth |  |  |  |  |  |

Derive the controller's transition rules from `controller.c` and
`controller.st`; do not copy a rule table from this reference. Your explanation
must cover both comparisons, the equality cases, and the role of prior state.
Use at least one multi-step input sequence, since isolated inputs cannot expose
retained-state behavior. `representation_check.py` uses six sequences as a
bounded equivalence check, not as a substitute for your explanation.

## Address note

The compact `%MD0`/`%QX0.0` mapping is local to this teaching controller. It
follows the same OpenPLC convention verified in the water-treatment mapping:
`%MD0` maps to two writable holding registers beginning at 2048 and `%QX0.0`
maps to writable coil 0. It does not claim that the full SWaT program uses
these two tags for the same simplified tank.

The backend writes both REAL words in one FC16 transaction. Splitting the pair
into independent writes could expose a torn intermediate float and is not part
of the student capability. Live readback of 50.0% produced words `16968, 0`
and decoded back to 50.0%, confirming the selected word order.
