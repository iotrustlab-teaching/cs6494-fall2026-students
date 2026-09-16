# HW2 controller representation map

One stateful decision is shown in several representations because each view
answers a different question. They are not interchangeable evidence.

| Concept | C/Python view | IEC ST variable | OpenPLC location | Modbus object/address | Wire encoding | Direction, owner, readers | Physical meaning |
|---|---|---|---|---|---|---|---|
| Reported observation | `reported_level_pct` / `reported_level` | `reported_level_pct` | `%MD0` | holding registers 2048–2049 | IEEE-754 binary32, big-endian bytes, high word first; one FC16 pair write | process writes; OpenPLC and process read | What the controller is told, not ground truth |
| Low threshold | `LOW_LEVEL_PCT` / `LOW_LEVEL = 45` | `LOW_LEVEL_PCT` | internal | not transferred | n/a | controller owns and reads | Below it, command OPEN |
| High threshold | `HIGH_LEVEL_PCT` / `HIGH_LEVEL = 55` | `HIGH_LEVEL_PCT` | internal | not transferred | n/a | controller owns and reads | Above it, command CLOSED |
| Prior command/state | `state.inlet_valve_open` / `controller.valve` | retained `inlet_valve_open` | `%QX0.0` | coil 0 | one Boolean bit | OpenPLC writes; process reads | State held inside the hysteresis band |
| Actuator command | return from `controller_step` / `valve` | `inlet_valve_open` | `%QX0.0` | coil 0 | one Boolean bit | OpenPLC writes; process reads and applies | Command applied to the simulated inlet |
| Process truth | intentionally absent / `tank.level` | intentionally absent | none | not exposed as controller truth | n/a | process owns; property oracle reads | Simulator-owned state used by the CPS oracle |

## Canonical transition contract

Initial command is CLOSED.

| Reported observation | Next command |
|---|---|
| `< 45%` | OPEN |
| `45% .. 55%`, including both boundaries | retain previous command |
| `> 55%` | CLOSED |

The boundaries and middle band make the controller stateful. Isolated test
values are insufficient; equivalence is checked over six input sequences by
`representation_check.py`.

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
