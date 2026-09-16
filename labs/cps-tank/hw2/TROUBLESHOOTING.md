# HW2 troubleshooting

Start with `./preflight.sh`. If a prepared SPHERE environment fails preflight,
copy the complete failed line to course staff; do not install packages or
invent a replacement port.

## `Permission denied` when running a script

Run it through Bash:

```bash
bash setup.sh
```

## Python is missing or too old

The scaffold needs Python 3.9 or newer and uses only the standard library. In the prepared SPHERE image it should already be installed. Locally, check with `python3 --version`.

## A staff equivalence check cannot find `cc`

Students do not compile C in HW2. The staff-only representation release check
compiles the small C controller; run that check on a staff development host.
The prepared process environment does not need a C compiler. OpenPLC's compiler
chain is independently available in the controller container.

## A run directory already exists

The runner refuses to overwrite evidence. Omit `--out` to get a timestamped directory, or choose a new empty path.

## The property checker returns status 1

That means the property verdict is `FAIL`; it does not mean the checker crashed. Read `property_results.json` for the first violating sample. Status 2 indicates a tooling or bundle error.

## Bundle validation reports a checksum mismatch

A file changed after collection. Keep the original bundle, make a copy for annotations, and rerun the case if you need pristine evidence.

## The SPHERE run has no packet capture

The primary SPHERE runner must create `network.pcap` and
`modbus_trace.csv`. If either is absent, stop and send the failed command to
staff. Do not substitute a screenshot or the local semantic trace.

## `network_trace.csv` exists but Wireshark cannot open it

That file belongs to the JSON/TCP fallback and is a semantic reconstruction,
not a pcap. In SPHERE, use `network.pcap` and its tshark-derived
`modbus_trace.csv` instead.

## A Modbus write is described as a program download

That classification is wrong for this lab. `%MD`/holding-register and
`%QX`/coil operations manipulate process data. OpenPLC program deployment uses
a separate engineering/management path. Recheck `REPRESENTATION_MAP.md` and
Part B of the assignment.

## SPHERE URL is unreachable

Check that the realization is materialized, the XDC is attached, the service is running, and the HTTP ingress still exists. URLs and tokens are deployment-specific; do not copy an old class URL from another realization.

If the XDC terminal itself works, run `./preflight.sh --require-sphere`. A
missing instance/team/expiry identity means the course image was not prepared
correctly and is a staff issue. Use the documented local fallback rather than
debugging SPHERE internals.

## Reset refuses to continue

Reset found a file it does not own in `.runtime` and stopped to protect it. Move the unexpected file yourself after inspecting it; the script will not delete student work.

## Reset did not delete my evidence

That is intentional. Every run begins with fresh in-memory controller and tank
state. Reset removes only recognized transient state; it retains evidence so
you can download or submit it.
