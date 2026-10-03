# Utility OT Security Workbench

An offline, fictional municipal-water-utility investigation. Students start
with network visibility, form an asset and communication map, test proposed
group-based network rules, then add controller and process evidence to make a
bounded cyber-physical security claim.

The workflow is **inspired by Cisco Cyber Vision, not Cisco Cyber Vision**. It
does not use Cisco software, logos, proprietary datasets, switch enforcement,
or vendor risk scores. The course adds program semantics, physical state,
authority, service, and recovery evidence beyond the network view.

## Start

```sh
./run_demo.sh
```

Open `http://127.0.0.1:8766/`. Set `PORT=8767` if that port is occupied. The
server binds to localhost. For an offline, no-server fallback, open `index.html`
directly. All data and scripts are local. There is no login or shared mutable
backend. Group assignments, proposed rules, criticality assessments, and notes
remain only in this browser. Download the notebook to keep a copy.

The guided path shows one investigation question at a time. The full packet
timeline, site layout, rule list, and controller code remain available in
expandable evidence sections when needed.

The companion [worksheet](WORKSHEET.md) is a classroom exercise, not the
official HW3 assignment or deadline notice.

## Evidence model

| Layer | Provenance and limit |
|---|---|
| Packet endpoints and exchanges | Ten **synthetic** Modbus/TCP packets in `data/monday-synthetic.pcap`, decoded with TShark into `traffic.json` / `traffic.js`; not a live capture |
| Initial assets | Three IP/MAC endpoints genuinely present in that packet fixture; protocol and first/last seen derive from the decoded events |
| Site record | Six additional **unverified leads**, plus names, roles and process areas for all nine records; none of those identities is authenticated by packets |
| Communication map | Two observed client-to-controller paths; no fabricated traffic for unverified leads |
| Segmentation | Local first-match allow/deny **what-if** calculation on frozen requests plus one explicitly authored legitimate-service test; no switch or firewall is changed |
| Controller | Illustrative Structured Text and register map authored for the exercise; not compiled or executed in this workbench |
| Process | Fixed authored simulation outcomes for transfer skid 04; no physical device or live telemetry |
| Challenge | Authored stale-valve-feedback case; report age is 30 seconds |

The fictional site spans source/intake, treatment, clearwell/storage, transfer,
and distribution. Only the transfer-skid subset has packet and rich process
evidence. The unused site-record IPs are documentation-only `192.0.2.0/24`
addresses, not extra discovered hosts. The packet fixture does not contain the
HW2 tank solution, credentials, or live infrastructure details.

## Verify or rebuild

TShark is needed to verify or rebuild the fixture, **not** to use the browser
workbench. Node is used for the small policy/scenario checks when available.

```sh
./run_demo.sh check
./run_demo.sh rebuild
```

The builder constructs valid Ethernet/IP/TCP Modbus packets with the Python
standard library and requires TShark to decode every packet before writing the
normalized browser event data. `static/policy.js` is the local, testable
policy-impact model. It intentionally does not decide physical safety. The
normalized event fields and future-adapter boundary are in
[EVENT_SCHEMA.md](EVENT_SCHEMA.md).

Zeek, Suricata, a staff agent, IEC-104, Cisco hosting, and SPHERE are not
required or connected. The separate Substation Recovery Lab remains another
development/demo track.
