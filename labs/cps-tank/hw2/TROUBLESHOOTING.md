# HW2 troubleshooting

Start with `./sphere/hw2-sphere status` on your workstation, then
`./preflight.sh --require-sphere` on your SPHERE process node. Use
`./preflight.sh` only in an instructor-authorized local fallback. If a
prepared SPHERE environment fails preflight,
copy the complete failed line to course staff; do not install packages or
invent a replacement port.

## `Permission denied` when running a script

Run it through Bash:

```bash
bash preflight.sh --require-sphere
```

Use `bash preflight.sh` without the flag only for the authorized local
fallback. The student release does not contain a `setup.sh` script.

## Python is missing or too old

The scaffold needs Python 3.9 or newer. The local fallback uses Python's
standard library; the prepared SPHERE process node also provides `pymodbus`,
`tcpdump`, and `tshark`. Locally, check with `python3 --version`.

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

## I am unsure how to classify a Modbus operation

Use the function, object type, address, endpoints, and observed effect to argue
for a process/data-plane or engineering/program-management classification.
Compare the captured operation with the separately documented OpenPLC
deployment path. Recheck `REPRESENTATION_MAP.md` and Part B, but supply the
classification and evidence-based explanation yourself.

## SPHERE URL is unreachable

Run `./sphere/hw2-sphere status` on your workstation. If your allocation
expired, run `create` again to obtain a fresh environment. Do not copy an old
class URL or another student's XDC URL.

Use `./sphere/hw2-sphere connect` to reach your **process-node shell**, run
`hw2-prepare`, enter the printed HW2 directory, then run
`./preflight.sh --require-sphere`. Do not run the lab on the XDC shell itself.
A missing instance/allocation/expiry value means provisioning did not finish;
leave the node and rerun `./sphere/hw2-sphere create` to resume it. Use the
documented local fallback only when staff authorize it.

## Self-service creation stops partway through

Run `./sphere/hw2-sphere status`, then rerun
`./sphere/hw2-sphere create`. The wrapper recognizes only the realization and
personal XDC derived from your authenticated SPHERE username and resumes the
fixed setup. If the existing realization reports an unexpected model revision,
release it and contact staff rather than overriding the check.

## Reset refuses to continue

In the local fallback, reset may find a file it does not own in `.runtime` and
stop to protect it. Inspect the unexpected file and ask staff before moving
anything. In SPHERE, reset can instead fail if it cannot reach OpenPLC or
verify that coil 0 is CLOSED; stop running cases and send the failed line to
staff.

## Reset did not delete my evidence

That is intentional. The local path removes only recognized transient state;
the SPHERE path restores the stateful OpenPLC CLOSED baseline. Both retain
evidence so you can download or submit it.
