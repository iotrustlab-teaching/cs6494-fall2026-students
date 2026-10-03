# Normalized event boundary

The browser reads `data/traffic.js`, a JavaScript wrapper around the checked-in
`data/traffic.json`. Both are built from the PCAP by `tools/build_fixture.py`
using TShark. This is the **only implemented adapter**.

Each `events[]` entry has:

| Field | Meaning |
|---|---|
| `packet`, `seconds` | Evidence reference and time relative to the fixture start |
| `evidence_source` | Exact adapter/provenance label; currently `synthetic-pcap:tshark` |
| `protocol` | Decoded protocol, currently `Modbus/TCP` |
| `operation` | Normalized `read` or `write` class for the simple policy exercise |
| `source`, `destination` | Packet-observed IP endpoints |
| `source_mac`, `destination_mac` | Packet-observed Ethernet addresses |
| `direction` | Request or response in the decoded exchange |
| `function`, `address`, `value`, `data` | Modbus-specific decoded details; nullable when absent from the PDU |
| `port` | TCP destination port in that packet |

An alternate importer would need to produce the same normalized endpoint,
time, protocol, operation, direction, and provenance fields and preserve a
source-native evidence reference. It must **not** infer physical effect, asset
identity, or authority from an operation class. Protocol-specific details can
be carried in separate optional fields. The current browser displays the
Modbus-specific fields and would need a renderer for a new protocol; this
contract is an extension point, **not** a claim that Cyber Vision, Zeek,
Suricata, or live lab import is implemented.

Asset names, roles, process areas, groups, register meanings, and authored
controller/process cases live separately in `data/scenario.js`. A packet
endpoint becomes a verified physical asset only with additional evidence.
