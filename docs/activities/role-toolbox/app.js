"use strict";

const STORAGE_KEY = "cs6494-role-toolbox-2026-10-19";
const HW3_URL = "https://hw3pilot-lgarcia.xdc.sphere-testbed.net/jupyter/substation/";
const ROLES = ["network", "program", "operator", "integrator"];
const ROLE_TITLES = {network:"Network",program:"Program",operator:"Operator",integrator:"Integrator"};
const $ = id => document.getElementById(id);

const CASES = {
  fixture: {
    label: "FICTIONAL TRANSFER SKID",
    source: "SYNTHETIC / AUTHORED",
    description: "This self-contained case uses invented packets, code, and process records. It is not a live utility or CTF incident.",
    roles: {
      network: {
        question: "Which request reached the controller, and what can the reply prove?",
        instruction: "Inspect the packet references, then test one proposed network rule against both unwanted and ordinary traffic.",
        artifact: `<h3>Packet view</h3><span class="evidence-tag">SYNTHETIC TSHARK-DECODED FIXTURE</span><table class="evidence-table"><thead><tr><th>Packet</th><th>Source → target</th><th>Operation</th><th>Visible result</th></tr></thead><tbody><tr><td>#5</td><td>192.0.2.11 → 192.0.2.20</td><td>Modbus write, register 120</td><td>Request sent</td></tr><tr><td>#6</td><td>192.0.2.20 → 192.0.2.11</td><td>Normal Modbus response</td><td>Protocol reply; no device feedback</td></tr><tr><td>#8</td><td>192.0.2.20 → 192.0.2.31</td><td>Reported state</td><td>Separate report; provenance differs</td></tr></tbody></table><p>Site-record names and roles are supplied leads, not authenticated identities from these packets.</p>`,
        tool: `<h3>Network policy what-if</h3><label for="policy">Proposed first-match rule<select id="policy"><option value="none">No new rule</option><option value="deny-all">Deny all controller traffic</option><option value="deny-write">Deny write to register 120</option><option value="deny-client">Deny all traffic from 192.0.2.11</option></select></label><div id="policy-result" class="tool-output" role="status"></div>`
      },
      program: {
        question: "Where could a valid write become a device command?",
        instruction: "Trace the authored input, condition, and output. This excerpt is not a verified running PLC build.",
        artifact: `<h3>Illustrative controller slice</h3><span class="evidence-tag">AUTHORED ST EXCERPT; NOT EXECUTED</span><pre><code>CloseRequest := HoldingRegister120;
PermitClose := CloseRequest AND PresentFlow_Lps &lt; Limit_Lps;
PumpStartOutput := PermitClose;</code></pre><div class="mini-flow"><span>Register 120</span><i>→</i><span>PermitClose</span><i>→</i><span>PumpStartOutput</span></div><p>Packet #6 does not identify the compiled build, prove <code>PermitClose</code> was true, or show a contactor changing state.</p>`,
        tool: `<h3>Program-analysis prompt</h3><p>Find the input, permissive, and output above. What state is absent if a transition changes what the pump would feed? Record a discriminating test and the build/run identity you would require.</p>`
      },
      operator: {
        question: "What did the operator see, and was that state still fresh?",
        instruction: "Compare report time with decision time before treating displayed feedback as current plant state.",
        artifact: `<h3>Operator and process record</h3><span class="evidence-tag">AUTHORED REPLAY</span><img class="process-figure" src="transfer-skid.svg" alt="Fictional process path: source vessel, V4 valve, P4 pump, service outlet"><table class="evidence-table"><thead><tr><th>Time</th><th>Record</th><th>Boundary</th></tr></thead><tbody><tr><td>t=00 s</td><td>Valve V4 reports OPEN</td><td>Reported state, not direct contact proof</td></tr><tr><td>t=24 s</td><td>V4 physically CLOSED in authored process model</td><td>Not yet reflected in HMI</td></tr><tr><td>t=30 s</td><td>Operator screen still shows last OPEN report</td><td>30-second-old data</td></tr></tbody></table><p>Do not infer service from a request or from a stale screen value.</p>`,
        tool: `<h3>Freshness check</h3><label for="max-age">Maximum acceptable report age<select id="max-age"><option value="5">5 seconds</option><option value="20">20 seconds</option><option value="45">45 seconds</option></select></label><div id="age-result" class="tool-output" role="status"></div>`
      },
      integrator: {
        question: "Which links in the claim have independent evidence?",
        instruction: "Keep packet response, program authorization, actual device feedback, and service outcome separate.",
        artifact: `<h3>Evidence chain</h3><span class="evidence-tag">MIXED PROVENANCE</span><div class="mini-flow"><span>Packet #5<br>request</span><i>→</i><span>Packet #6<br>reply</span><i>→</i><span>Authored ST<br>decision path</span><i>→</i><span>Authored replay<br>device state</span><i>→</i><span>Service claim<br>needs testing</span></div><p>These are not all observations from one executed run. A protocol reply and a source excerpt cannot be joined into a verified actuation claim without build, runtime, device, and time alignment.</p>`,
        tool: `<h3>Integration check</h3><p>Ask each teammate for one cited fact and one limit. In the team synthesis, write the narrowest claim you can support, then name a test that could falsify it.</p>`
      }
    }
  },
  hw3: {
    label: "HW3 OPENPLC WORKSPACE",
    source: "LIVE SOFTWARE CONTROLLER; YOUR OWN RUN",
    description: "The linked HW3 workspace runs compiled OpenPLC in an isolated SPHERE class environment. This toolbox stores only your notes and does not read or control that workspace.",
    roles: {
      network: {question:"What communication evidence is available for your HW3 test?",instruction:"Open your personal workspace. Separate a request in the app's evidence from any actual packet capture; do not claim IEC-104 traffic unless it is captured.",artifact:`<h3>Your evidence path</h3><span class="evidence-tag">LIVE HW3 WORKSPACE; THIS PAGE IS NOT CONNECTED</span><p><a href="${HW3_URL}" target="_blank" rel="noopener noreferrer">Open HW3 in a new tab</a> with your own personal code. Record the test case, run ID, and communication evidence the UI actually provides.</p><p>A request shown in an application trace is not automatically a network packet or a physical actuation.</p>`,tool:"<h3>Network task</h3><p>Find one request and one response/decision in your own run. Which endpoint identity and protocol details are directly recorded? Which are not?</p>"},
      program: {question:"Does the source match the executed controller build?",instruction:"Use your personal HW3 workspace to inspect source, compile, and run one bounded case. Do not paste a teammate's result as your own.",artifact:`<h3>Controller path</h3><span class="evidence-tag">LIVE COMPILED OPENPLC V3 IN SEPARATE WORKSPACE</span><p><a href="${HW3_URL}" target="_blank" rel="noopener noreferrer">Open HW3 in a new tab</a>. Record the source/build identifier and the run ID for a prohibited request and a legitimate restoration request.</p><p>Trace request input → permissive → output. Keep the reference repair and your specific code out of a public handoff.</p>`,tool:"<h3>Program task</h3><p>Does a source line alone prove the decision that ran? What build and event IDs would make the test reproducible?</p>"},
      operator: {question:"What did the controller report versus what did the process do?",instruction:"Use a run from your own HW3 workspace and distinguish request, controller decision, breaker position, and energized service.",artifact:`<h3>State and service</h3><span class="evidence-tag">LIVE SOFTWARE SIMULATION; NOT A PHYSICAL SUBSTATION</span><p><a href="${HW3_URL}" target="_blank" rel="noopener noreferrer">Open HW3 in a new tab</a>. Compare the displayed breaker position and circuit outcome for one prohibited and one legitimate request.</p><p>Record run ID and whether the interface shows actual model state, a requested state, or an inference.</p>`,tool:"<h3>Operator task</h3><p>What would an operator need to know before restoration? Name one stale or missing observation that would change your conclusion.</p>"},
      integrator: {question:"Can your team's two HW3 tests support both safety and service?",instruction:"Use matched build and run IDs. A deny-all repair is not a successful restoration result.",artifact:`<h3>Two-run contract</h3><span class="evidence-tag">LIVE SOFTWARE SIMULATION; YOUR OWN EVIDENCE</span><p><a href="${HW3_URL}" target="_blank" rel="noopener noreferrer">Open HW3 in a new tab</a>. Bring together the prohibited-transition case and the healthy-restoration case. Compare build identity, decisions, device positions, and service results.</p>`,tool:"<h3>Integration task</h3><p>Write one claim supported by both tests, plus an assumption that a later changed state could invalidate. Do not treat this practice handoff as an HW3 submission.</p>"}
    }
  }
};

function emptyState() { return {implementation:"fixture",role:"network",notes:{fixture:{},hw3:{}},teamClaim:"",nextTest:"",policy:"none",maxAge:"5"}; }
function readState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (!parsed || !CASES[parsed.implementation] || !ROLES.includes(parsed.role)) return emptyState();
    return {...emptyState(), ...parsed, notes:{fixture:parsed.notes?.fixture || {},hw3:parsed.notes?.hw3 || {}}};
  } catch { return emptyState(); }
}
let state = readState();
function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); $("saved").textContent = "Saved in this browser"; }
  catch { $("saved").textContent = "Browser storage unavailable. Download your notes before leaving."; }
}
function storeCurrentNote() {
  state.notes[state.implementation][state.role] = {fact:$("fact").value,citation:$("citation").value,limit:$("limit").value};
  persist();
}
function renderPolicy() {
  const rule = $("policy"); if (!rule) return;
  rule.value = state.policy;
  const unwanted = state.policy === "deny-all" || state.policy === "deny-write" || state.policy === "deny-client";
  const service = state.policy === "deny-all";
  $("policy-result").innerHTML = `<div>Write to register 120: <span class="${unwanted ? "fail" : "pass"}">${unwanted ? "BLOCKED" : "ALLOWED"}</span></div><div>Ordinary service read: <span class="${service ? "fail" : "pass"}">${service ? "BLOCKED" : "ALLOWED"}</span></div><div class="minor">Local first-match teaching model only. A network permit is not controller authorization.</div>`;
  rule.onchange = () => { state.policy = rule.value; persist(); renderPolicy(); };
}
function renderAge() {
  const choice = $("max-age"); if (!choice) return;
  choice.value = state.maxAge;
  const stale = 30 > Number(state.maxAge);
  $("age-result").innerHTML = `<div>Last OPEN report at t=00 s; decision at t=30 s. Age: <strong>30 s</strong>.</div><div>Under this rule: <span class="${stale ? "fail" : "warn"}">${stale ? "STALE; do not rely on it" : "WITHIN AGE LIMIT; still not physical proof"}</span></div>`;
  choice.onchange = () => { state.maxAge = choice.value; persist(); renderAge(); };
}
function render() {
  const spec = CASES[state.implementation], role = spec.roles[state.role], note = state.notes[state.implementation][state.role] || {};
  $("implementation").value = state.implementation;
  $("source-label").textContent = spec.source;
  $("source-description").textContent = spec.description;
  $("source-label").parentElement.style.borderLeftColor = state.implementation === "hw3" ? "#0d695e" : "#845b19";
  $("role-count").textContent = `${String(ROLES.indexOf(state.role)+1).padStart(2,"0")} / 04`;
  $("case-badge").textContent = spec.label;
  $("question").textContent = role.question;
  $("instruction").textContent = role.instruction;
  $("artifact").innerHTML = role.artifact;
  $("tool").innerHTML = role.tool;
  for (const button of document.querySelectorAll("[data-role]")) button.setAttribute("aria-pressed", String(button.dataset.role === state.role));
  $("fact").value = note.fact || ""; $("citation").value = note.citation || ""; $("limit").value = note.limit || "";
  $("team-claim").value = state.teamClaim; $("next-test").value = state.nextTest;
  $("saved").textContent = "";
  renderPolicy(); renderAge();
}
function switchRole(role) { storeCurrentNote(); state.role = role; persist(); render(); }
function handoffText() {
  const n = state.notes[state.implementation][state.role] || {};
  return `CS 6494 ${ROLE_TITLES[state.role]} handoff (${CASES[state.implementation].label})\nEvidence class: ${CASES[state.implementation].source}\nEstablished: ${n.fact || "[not recorded]"}\nCitation: ${n.citation || "[not recorded]"}\nDoes not prove: ${n.limit || "[not recorded]"}\nPractice only; not an HW3 or CTF submission.`;
}
function downloadNotes() {
  storeCurrentNote();
  const clean = {activity:"CS 6494 CPS Evidence Toolbox",practiceOnly:true,generatedAt:new Date().toISOString(),implementation:state.implementation,notes:state.notes,teamClaim:state.teamClaim,nextTest:state.nextTest};
  const url = URL.createObjectURL(new Blob([JSON.stringify(clean,null,2)],{type:"application/json"}));
  const a = document.createElement("a"); a.href = url; a.download = "cs6494-toolbox-notes.json"; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("implementation").onchange = event => { storeCurrentNote(); state.implementation = event.target.value; persist(); render(); };
for (const button of document.querySelectorAll("[data-role]")) button.onclick = () => switchRole(button.dataset.role);
for (const id of ["fact","citation","limit"]) $(id).addEventListener("input", storeCurrentNote);
$("team-claim").oninput = event => { state.teamClaim = event.target.value; persist(); };
$("next-test").oninput = event => { state.nextTest = event.target.value; persist(); };
$("previous").onclick = () => switchRole(ROLES[(ROLES.indexOf(state.role)+ROLES.length-1)%ROLES.length]);
$("next").onclick = () => switchRole(ROLES[(ROLES.indexOf(state.role)+1)%ROLES.length]);
$("copy").onclick = async () => {
  storeCurrentNote();
  try { await navigator.clipboard.writeText(handoffText()); $("saved").textContent = "Handoff copied"; }
  catch { $("saved").textContent = "Clipboard unavailable here. Download notes instead."; }
};
$("export").onclick = downloadNotes;
render();
