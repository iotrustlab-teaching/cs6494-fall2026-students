# CTF Prep Workbench

An offline-capable browser exercise about OT visibility, controller authority,
physical consequence, and evidence. The OT visibility view is inspired by the
teaching abstraction of an industrial asset/flow map. **This is not Cisco Cyber
Vision** and does not reproduce that product.

## Start

From this directory:

```sh
./run_demo.sh
```

Open `http://127.0.0.1:8766/`. Set `PORT=8767` (or another free local port)
if needed. No account, network connection, package installation, or mutable
server state is needed. The server binds only to localhost. For a no-server
fallback, open `index.html` directly in a browser; all data is bundled in local
scripts, so `file://` also works.

The activity materials are in [WORKSHEET.md](WORKSHEET.md). The browser's notes
remain in local browser storage and can be downloaded as Markdown. They are not
submitted or shared automatically.

## Evidence boundary

| Component | What it really is |
|---|---|
| `data/monday-synthetic.pcap` | Constructed Modbus/TCP packet fixture, not live capture |
| `data/traffic.json` / `.js` | Decoded from that PCAP with TShark; ten packets |
| Asset names, register meanings | Fictional exercise manifest, not packet-derived identity |
| Controller view | Authored illustrative ST source, not compiled or executed here |
| Process view | Authored fixed simulation outcomes, not physical telemetry |
| Replay cases | Fixed teaching traces, not new results from running student code |
| Staff agent, IEC-104, Cisco host | Not connected to this workbench |

The Modbus address map is **not** the HW2 tank map, and the capture contains no
HW2 solution or credentials. The addresses use documentation-only `192.0.2.0/24`.

The browser distinguishes request, protocol acknowledgment, controller decision,
reported state, and physical outcome. A successful write response alone does not
prove safe actuation.

## Verify or rebuild the fixture

TShark is only required to verify or rebuild the frozen capture, not to run the
browser activity.

```sh
./run_demo.sh check
./run_demo.sh rebuild
```

The builder uses only the Python standard library to construct Ethernet/IP/TCP
frames with Modbus/TCP payloads, then requires TShark to decode every packet.
The checked-in browser event data comes from the TShark decoder. Optional Zeek
or Suricata inputs are not qualified or required.

The separate Substation Recovery Lab remains a development/demo track, not a
dependency for this activity. Official HW3 requirements and due dates must come
from the course announcement or Canvas.
