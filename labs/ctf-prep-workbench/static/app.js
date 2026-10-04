(() => {
  "use strict";
  const traffic = window.WORKBENCH_TRAFFIC;
  const scenario = window.WORKBENCH_SCENARIO;
  const policy = window.WORKBENCH_POLICY;
  const views = ["overview", "assets", "communications", "assurance", "segmentation", "challenge"];
  const byId = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
  const observedIps = new Set(traffic.events.flatMap((event) => [event.source, event.destination]));
  const observed = scenario.assets.filter((asset) => observedIps.has(asset.ip));
  const leads = scenario.assets.filter((asset) => !observedIps.has(asset.ip));
  const requestEvents = traffic.events.filter((event) => event.direction === "request");
  const storageKey = "utilityOtWorkbenchStateV2";
  const noteKey = "utilityOtWorkbenchNotesV1";
  const state = {
    view: "overview", unlocked: 2, explore: false, manifestOpen: false, selectedAsset: observed[0].ip,
    selectedFlow: "192.0.2.11|192.0.2.20", selectedCandidate: null, mapMode: "assets", operationFilter: "all",
    groups: Object.fromEntries(scenario.assets.map((asset) => [asset.ip, "Unassigned"])),
    criticality: {}, rules: [], selectedCase: "baseline"
  };

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      if (saved.groups && typeof saved.groups === "object") {
        for (const asset of scenario.assets) if (policy.GROUPS.includes(saved.groups[asset.ip])) state.groups[asset.ip] = saved.groups[asset.ip];
      }
      if (saved.criticality && typeof saved.criticality === "object") state.criticality = saved.criticality;
      if (saved.manifestOpen === true) state.manifestOpen = true;
      if (Number.isInteger(saved.unlocked) && saved.unlocked >= 2 && saved.unlocked < views.length) state.unlocked = saved.unlocked;
      if (requestEvents.some((event) => event.packet === saved.selectedCandidate)) state.selectedCandidate = saved.selectedCandidate;
      if (views.includes(saved.view) && views.indexOf(saved.view) <= state.unlocked) state.view = saved.view;
      if (Array.isArray(saved.rules)) state.rules = saved.rules.filter((rule) =>
        rule && typeof rule.id === "string" && ["allow", "deny"].includes(rule.action) &&
        ["any", "write", "read"].includes(rule.operation) &&
        ["Any", ...policy.GROUPS].includes(rule.source) && ["Any", ...policy.GROUPS].includes(rule.destination)
      ).slice(0, 20);
    } catch (_) { /* Browser storage can be unavailable. */ }
  }
  function saveState() {
    try { localStorage.setItem(storageKey, JSON.stringify({ groups: state.groups, criticality: state.criticality, rules: state.rules,
      manifestOpen: state.manifestOpen, unlocked: state.unlocked, selectedCandidate: state.selectedCandidate, view: state.view })); } catch (_) { /* Local only. */ }
  }
  function showView(view) {
    const index = views.indexOf(view);
    if (index < 0 || index > state.unlocked) return;
    state.view = view;
    document.querySelectorAll(".view").forEach((section) => section.classList.toggle("active", section.id === `view-${view}`));
    document.querySelectorAll(".tabs button").forEach((button) => {
      const active = button.dataset.view === view;
      button.hidden = views.indexOf(button.dataset.view) > state.unlocked + 1;
      button.classList.toggle("active", active);
      button.disabled = views.indexOf(button.dataset.view) > state.unlocked;
      if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
    });
    saveState();
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  function unlock(view) { state.unlocked = Math.max(state.unlocked, views.indexOf(view)); showView(view); }
  function isObserved(asset) { return observedIps.has(asset.ip); }
  function eventsFor(asset) { return traffic.events.filter((event) => event.source === asset.ip || event.destination === asset.ip); }
  function macFor(asset) {
    const event = eventsFor(asset)[0];
    return event ? (event.source === asset.ip ? event.source_mac : event.destination_mac) : null;
  }
  function packetValue(event) {
    if (event.value !== null) return String(event.value);
    if (event.function === 6 && event.data) return String(parseInt(event.data, 16));
    return "—";
  }
  function operationLabel(event) {
    if (event.function === 6) return event.direction === "request" ? "Write single register" : "Write response";
    return event.direction === "request" ? "Read holding register" : "Read response";
  }
  function packetRole(asset) {
    if (!isObserved(asset)) return "Not observed";
    const sends = requestEvents.some((event) => event.source === asset.ip);
    const receives = requestEvents.some((event) => event.destination === asset.ip);
    if (sends && !receives) return "Modbus client candidate";
    if (receives && !sends) return "Modbus server candidate";
    return "Modbus endpoint; role unresolved";
  }

  function renderOverview() {
    byId("metric-observed").textContent = observed.length;
    byId("metric-leads").textContent = leads.length;
    byId("metric-writes").textContent = requestEvents.filter((event) => policy.operation(event) === "write").length;
    byId("overview-flows").innerHTML = rawFlows.map((flow) => `<div class="overview-flow"><code>${esc(flow.source)}</code><span>Modbus/TCP <b aria-hidden="true">→</b></span><code>${esc(flow.destination)}</code></div>`).join("");
    byId("site-layout").hidden = !state.manifestOpen;
    byId("utility-chain").innerHTML = scenario.areas.map((area, index) => `
      <div class="chain-stage ${state.manifestOpen && area === "Transfer skid" ? "chain-focus" : ""}">
        <small>AREA ${String(index + 1).padStart(2, "0")}</small><b>${state.manifestOpen ? esc(area) : "Unverified area"}</b>
        <span>${state.manifestOpen && area === "Transfer skid" ? "process context available" : "site record not validated"}</span>
      </div>${index < scenario.areas.length - 1 ? '<span class="chain-arrow">→</span>' : ""}`).join("");
    byId("map-status").textContent = state.manifestOpen ? "Site-record layout opened · only transfer-skid traffic observed" : "Site layout withheld · packet evidence covers one unknown cell";
  }

  function visibleAssets() { return state.manifestOpen ? scenario.assets : observed; }
  function setAssetGroup(ip, group) {
    state.groups[ip] = group;
    saveState(); renderAssets(); renderGroups(); renderMap(); renderSimulation(); renderGroupReadiness();
  }
  function renderAssets() {
    const query = byId("asset-search").value.trim().toLowerCase();
    const showAll = state.manifestOpen && byId("asset-filter").value === "all";
    const records = (showAll ? scenario.assets : observed).filter((asset) =>
      [asset.id, asset.ip, asset.name, asset.role].some((value) => value.toLowerCase().includes(query))
    );
    byId("asset-filter").querySelector('option[value="all"]').disabled = !state.manifestOpen;
    byId("asset-rows").innerHTML = records.map((asset) => `<tr class="asset-row ${state.selectedAsset === asset.ip ? "selected" : ""}" tabindex="0" data-ip="${esc(asset.ip)}">
      <td><code>${esc(asset.ip)}</code><small>${isObserved(asset) ? esc(macFor(asset)) : "Site-record IP; not in packets"}</small></td>
      <td><span class="badge ${isObserved(asset) ? "observed" : "supplied"}">${isObserved(asset) ? "PACKET" : "NOT SEEN"}</span><small>${esc(packetRole(asset))}</small></td>
      <td>${state.manifestOpen ? `<span class="badge supplied">SUPPLIED</span><small>${esc(asset.id)} · ${esc(asset.name)} · ${esc(asset.role)}</small>` : "Withheld"}</td>
      <td>${esc(state.groups[asset.ip])}</td><td>${esc(state.criticality[asset.ip] || "Unassessed")}</td></tr>`).join("") || '<tr><td colspan="5">No assets match this filter.</td></tr>';
    document.querySelectorAll(".asset-row").forEach((row) => {
      const select = () => { state.selectedAsset = row.dataset.ip; renderAssets(); };
      row.addEventListener("click", select);
      row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } });
    });
    const asset = scenario.assets.find((item) => item.ip === state.selectedAsset) || observed[0];
    const events = eventsFor(asset);
    byId("selected-asset-id").textContent = state.manifestOpen ? asset.id : asset.ip;
    const seen = events.length ? `${events[0].seconds.toFixed(2)}–${events[events.length - 1].seconds.toFixed(2)} s` : "Not seen in capture";
    const peers = [...new Set(events.map((event) => event.source === asset.ip ? event.destination : event.source))];
    const groupOptions = policy.GROUPS.map((group) => `<option ${state.groups[asset.ip] === group ? "selected" : ""}>${esc(group)}</option>`).join("");
    const criticalityOptions = ["Unassessed", "Low", "Medium", "High"].map((level) => `<option ${state.criticality[asset.ip] === level ? "selected" : ""}>${level}</option>`).join("");
    byId("asset-detail").innerHTML = `
      <div class="sheet-block"><span class="sheet-label">OBSERVED FROM PACKETS</span>
        <dl><dt>IP</dt><dd>${isObserved(asset) ? esc(asset.ip) : "Not observed"}</dd><dt>MAC</dt><dd>${macFor(asset) || "Not observed"}</dd>
        <dt>Protocol</dt><dd>${isObserved(asset) ? "Modbus/TCP" : "Not observed"}</dd><dt>First / last</dt><dd>${seen}</dd>
        <dt>Packet role</dt><dd>${esc(packetRole(asset))}</dd><dt>Peers</dt><dd>${peers.length ? peers.map(esc).join(", ") : "None observed"}</dd><dt>Packets</dt><dd>${events.map((event) => `#${event.packet}`).join(", ") || "None"}</dd></dl></div>
      <div class="sheet-block"><span class="sheet-label supplied-text">SUPPLIED SITE RECORD</span>
        <p>${state.manifestOpen ? `${esc(asset.name)} · ${esc(asset.role)} · ${esc(asset.area)}. Suggested group: ${esc(asset.group)}.` : "Open the site record to compare names and roles with packet evidence."}</p>
        ${state.manifestOpen && asset.group !== "Unassigned" ? '<button type="button" id="use-suggested-group" class="secondary-action">Use suggested group</button>' : ""}</div>
      <div class="sheet-block"><span class="sheet-label">UNKNOWN / STUDENT ASSESSMENT</span>
        <p>Vendor, model, firmware, exact program and physical authority are not established by these packets.</p>
        <label>Your assigned group<select id="asset-group" ${state.manifestOpen ? "" : "disabled"}>${groupOptions}</select></label>
        <label>Process criticality<select id="asset-criticality">${criticalityOptions}</select></label></div>`;
    byId("asset-group").addEventListener("change", (event) => setAssetGroup(asset.ip, event.target.value));
    byId("use-suggested-group")?.addEventListener("click", () => setAssetGroup(asset.ip, asset.group));
    byId("asset-criticality").addEventListener("change", (event) => { state.criticality[asset.ip] = event.target.value; saveState(); renderAssets(); });
    byId("manifest-status").textContent = state.manifestOpen ? "Site record opened · unverified leads visible" : "6 leads withheld";
    byId("open-manifest").disabled = state.manifestOpen;
    byId("open-manifest").textContent = state.manifestOpen ? "Site record opened" : "Open site record";
  }

  function flowPackets(source, destination) {
    return traffic.events.filter((event) => (event.source === source && event.destination === destination) || (event.source === destination && event.destination === source));
  }
  const rawFlows = [
    { source: "192.0.2.11", destination: "192.0.2.20" },
    { source: "192.0.2.31", destination: "192.0.2.20" }
  ];
  function filteredFlowPackets(flow) {
    const packets = flowPackets(flow.source, flow.destination);
    if (state.operationFilter === "all") return packets;
    const selectedRequests = packets.filter((event) => event.direction === "request" && policy.operation(event) === state.operationFilter);
    const packetNumbers = new Set(selectedRequests.flatMap((event) => [event.packet, event.packet + 1]));
    return packets.filter((event) => packetNumbers.has(event.packet));
  }
  function mapFlows() {
    const active = rawFlows.filter((flow) => filteredFlowPackets(flow).length);
    if (state.mapMode === "assets") return active.map((flow) => ({ ...flow, key: `${flow.source}|${flow.destination}`, packets: filteredFlowPackets(flow) }));
    const grouped = new Map();
    active.forEach((flow) => {
      const source = state.groups[flow.source];
      const destination = state.groups[flow.destination];
      const key = `${source}|${destination}`;
      if (!grouped.has(key)) grouped.set(key, { source, destination, key, packets: [] });
      grouped.get(key).packets.push(...filteredFlowPackets(flow));
    });
    return [...grouped.values()];
  }
  function renderMap() {
    const flows = mapFlows();
    const selected = flows.find((flow) => flow.key === state.selectedFlow) || flows[0];
    if (selected) state.selectedFlow = selected.key;
    byId("flow-map").innerHTML = flows.length ? flows.map((flow) => `<button type="button" class="flow-item ${flow.key === state.selectedFlow ? "selected" : ""}" data-flow="${esc(flow.key)}" aria-pressed="${flow.key === state.selectedFlow}" aria-label="Inspect ${esc(flow.source)} to ${esc(flow.destination)} path">
      <span class="flow-endpoint">${esc(flow.source)}</span><span class="flow-direction">→<small>Modbus/TCP · ${flow.packets.length} packets</small></span><span class="flow-endpoint">${esc(flow.destination)}</span></button>`).join("") : '<p class="surface-note">No paths match this operation filter.</p>';
    byId("flow-map").querySelectorAll("[data-flow]").forEach((button) => button.addEventListener("click", () => { state.selectedFlow = button.dataset.flow; renderMap(); }));
    byId("edge-detail").innerHTML = selected ? `<div class="edge-summary"><b>${esc(selected.source)} → ${esc(selected.destination)}</b><p>${selected.packets.length} packet-observed exchanges · Modbus/TCP</p><p>Names and process roles are supplied, not verified by these packets.</p></div>
      <div class="edge-packets">${selected.packets.map((event) => `<div><b>#${event.packet}</b><span>${esc(operationLabel(event))}${event.address !== null ? ` · reg ${event.address}` : ""}${packetValue(event) !== "—" ? ` · value ${esc(packetValue(event))}` : ""}</span></div>`).join("")}</div>` : '<p class="surface-note">No packets match this filter.</p>';
  }
  function responseFor(request) {
    return traffic.events.find((event) => event.direction === "response" && event.source === request.destination &&
      event.destination === request.source && event.function === request.function && event.packet === request.packet + 1);
  }
  function renderCandidate() {
    byId("candidate-packet").innerHTML = '<option value="" disabled>Choose a request</option>' + requestEvents.map((event) =>
      `<option value="${event.packet}">#${event.packet} · ${esc(policy.operation(event))} · target ${event.address}</option>`).join("");
    byId("candidate-packet").value = state.selectedCandidate ? String(state.selectedCandidate) : "";
    const request = requestEvents.find((event) => event.packet === state.selectedCandidate);
    const mapped = request?.packet === 5;
    const response = request && responseFor(request);
    byId("candidate-result").innerHTML = request ? `<div class="candidate-facts"><span><b>Requester</b>${esc(request.source)}</span><span><b>Operation</b>${esc(policy.operation(request))}</span><span><b>Target</b>${request.address}</span><span><b>Value</b>${esc(packetValue(request))}</span><span><b>Response</b>${response ? `#${response.packet}` : "Not seen"}</span></div>
      <p>${mapped ? `Packet #${response?.packet} is a normal Modbus FC06 echo consistent with processing the protocol write. It does not establish controller authorization, actuator motion, or a safe physical outcome.` : "This read request has no supplied command-to-process mapping in the exercise. Inspect the write candidate if you want to trace a possible state change."}</p>
      <p>A normal response confirms a protocol-level reply, not physical success. An exception or negative response would show protocol-level rejection or failure; neither response alone proves the device's physical state. No exception response appears in this trace.</p>
      <p class="surface-note">Modbus detail: FC${request.function}, register ${request.address}. The transferable fields are requester, operation, target, value, and response.</p>` : '<p class="surface-note">Select a packet request to make a bounded claim about it.</p>';
    byId("claim-notebook").hidden = !mapped;
    byId("open-assurance").disabled = !mapped;
  }
  function renderTraffic() {
    byId("traffic-rows").innerHTML = traffic.events.map((event) => `<tr><td>#${event.packet}</td><td>${event.seconds.toFixed(2)}</td>
      <td><code>${esc(event.source)} → ${esc(event.destination)}</code></td><td class="${event.function === 6 ? "write-op" : ""}">${esc(operationLabel(event))}</td>
      <td>${event.address ?? "—"}</td><td>${esc(packetValue(event))}</td></tr>`).join("");
  }

  function groupOptions() { return '<option value="" selected disabled>Choose group</option>' + ["Any", ...policy.GROUPS].map((group) => `<option value="${esc(group)}">${esc(group)}</option>`).join(""); }
  function renderGroupReadiness() {
    const ready = state.groups["192.0.2.11"] !== "Unassigned" && state.groups["192.0.2.20"] !== "Unassigned";
    byId("group-prereq").hidden = ready;
    byId("add-rule").disabled = !ready;
  }
  function renderGroups() {
    const grouped = new Map();
    visibleAssets().forEach((asset) => {
      const group = state.groups[asset.ip];
      if (!grouped.has(group)) grouped.set(group, []);
      grouped.get(group).push(asset);
    });
    byId("group-summary").innerHTML = [...grouped.entries()].map(([group, assets]) => `<div><b>${esc(group)}</b><span>${assets.map((asset) => `${esc(state.manifestOpen ? asset.id : asset.ip)}${isObserved(asset) ? "" : " *"}`).join(", ")}</span></div>`).join("");
  }
  function renderRules() {
    byId("rule-list").innerHTML = state.rules.length ? state.rules.map((rule, index) => `<div class="rule-item"><b>${index + 1}. ${esc(rule.action.toUpperCase())}</b><span>${esc(rule.source)} → ${esc(rule.destination)} · ${esc(rule.operation)}</span><button type="button" data-remove="${esc(rule.id)}" aria-label="Remove rule ${index + 1}">Remove</button></div>`).join("") : '<p class="surface-note">No proposed rules. Default action: allow.</p>';
    byId("rule-list").querySelectorAll("[data-remove]").forEach((button) => button.addEventListener("click", () => {
      state.rules = state.rules.filter((rule) => rule.id !== button.dataset.remove);
      saveState(); renderRules(); renderSimulation();
    }));
  }
  function renderSimulation() {
    const serviceTest = { source: "192.0.2.11", destination: "192.0.2.20", function: 6, address: 120, value: 1, origin: "Authored legitimate-service test" };
    const cases = requestEvents.map((event) => ({ ...event, origin: `PCAP #${event.packet}` })).concat(serviceTest);
    byId("simulation-rows").innerHTML = cases.map((event) => {
      const outcome = policy.evaluate(event, state.groups, state.rules);
      const service = event.origin === "Authored legitimate-service test";
      const verdict = service ? (outcome.action === "deny" ? "Legitimate service blocked" : "Service request network-permitted; delivery unproven") :
        event.packet === 5 ? (outcome.action === "deny" ? "Observed write would be blocked" : "Write network-permitted; safety unknown") :
        `${outcome.operation === "read" ? "Read" : "Write"} ${outcome.action === "deny" ? "would be blocked" : "network-permitted"}`;
      const ruleIndex = state.rules.findIndex((rule) => rule.id === outcome.rule);
      const ruleLabel = ruleIndex >= 0 ? `Rule ${ruleIndex + 1}` : "Default allow";
      return `<div class="impact-row"><div><b>${esc(event.origin)}</b><small>${esc(outcome.source)} → ${esc(outcome.destination)} · ${esc(outcome.operation)} · target ${event.address ?? "?"}</small></div>
        <div class="impact-verdict"><span class="badge ${outcome.action === "deny" ? "denied" : "allowed"}">${esc(outcome.action.toUpperCase())}</span><strong class="${service && outcome.action === "deny" ? "service-blocked" : ""}">${esc(verdict)}</strong></div><span class="impact-rule">${esc(ruleLabel)}</span></div>`;
    }).join("");
  }

  function timeline(steps) {
    return steps.map(([time, source, description]) => `<div class="event"><time>${esc(time)}</time><b>${esc(source)}</b><span>${esc(description)}</span></div>`).join("");
  }
  function renderCase(id) {
    const selected = scenario.cases.find((item) => item.id === id && id !== "stale") || scenario.cases[0];
    state.selectedCase = selected.id;
    byId("case-picker").querySelectorAll("button").forEach((button) => button.classList.toggle("active", button.dataset.case === selected.id));
    byId("case-summary").innerHTML = `<div class="case-body"><span class="badge authored">AUTHORED REPLAY</span><b>${esc(selected.label)}</b><p><strong>Initial state</strong> ${esc(selected.condition)}</p>
      <p><strong>Request</strong> ${esc(selected.command)}</p><p><strong>Decision</strong> ${esc(selected.decision)}</p>
      <p><strong>${selected.id === "baseline" ? "Packet-backed reports" : "Authored reports"}</strong> ${esc(selected.feedback)}</p><p><strong>Authored physical replay</strong> ${esc(selected.physical)}</p>
      <div class="case-outcomes"><span class="badge ${selected.safety === "Preserved" ? "allowed" : "denied"}">Safety: ${esc(selected.safety)}</span>
      <span class="badge ${selected.service === "Delivered" ? "allowed" : "supplied"}">Service: ${esc(selected.service)}</span></div></div>`;
    byId("case-timeline").innerHTML = timeline(selected.steps);
  }
  function renderAssurance() {
    byId("st-source").textContent = scenario.source;
    byId("register-rows").innerHTML = scenario.registers.map((item) => `<tr><td>${item.address}</td><td>${esc(item.label)}</td><td>${esc(item.source)}</td></tr>`).join("");
    byId("case-picker").innerHTML = scenario.cases.filter((item) => item.id !== "stale").map((item) => `<button type="button" data-case="${esc(item.id)}">${esc(item.label)}</button>`).join("");
    byId("case-picker").querySelectorAll("button").forEach((button) => button.addEventListener("click", () => renderCase(button.dataset.case)));
    renderCase(state.selectedCase);
    byId("challenge-timeline").innerHTML = timeline(scenario.cases.find((item) => item.id === "stale").steps);
  }

  function noteData() {
    return { claim: byId("claim").value, falsifier: byId("falsifier").value,
      positiveTest: byId("positive-test").value, unknown: byId("unknown").value, challenge: byId("challenge").value,
      controls: [...document.querySelectorAll("[data-control]:checked")].map((input) => input.dataset.control) };
  }
  function renderOriginalClaim() { byId("original-claim").textContent = byId("claim").value.trim() || "No working claim recorded yet."; }
  function loadNotes() {
    try {
      const notes = JSON.parse(localStorage.getItem(noteKey) || "{}");
      byId("claim").value = notes.claim || ""; byId("falsifier").value = notes.falsifier || "";
      byId("positive-test").value = notes.positiveTest || ""; byId("unknown").value = notes.unknown || "";
      byId("challenge").value = notes.challenge || "";
      document.querySelectorAll("[data-control]").forEach((input) => { input.checked = (notes.controls || []).includes(input.dataset.control); });
    } catch (_) { /* Export still works without storage. */ }
    renderOriginalClaim();
  }
  function saveNotes() { renderOriginalClaim(); try { localStorage.setItem(noteKey, JSON.stringify(noteData())); } catch (_) { /* Local only. */ } }
  function downloadNotes() {
    const notes = noteData();
    const body = `# Utility OT Security Workbench notes\n\nFixture: Riverbend Water Utility (fictional)\n\n## Assigned asset groups\n${scenario.assets.map((asset) => `- ${asset.id}: ${state.groups[asset.ip]} (${isObserved(asset) ? "packet endpoint" : "site record only"})`).join("\n")}\n\n## Process criticality assessment\n${scenario.assets.map((asset) => `- ${asset.id}: ${state.criticality[asset.ip] || "Unassessed"}`).join("\n")}\n\n## Proposed network rules\n${state.rules.map((rule) => `- ${rule.action} ${rule.source} -> ${rule.destination} ${rule.operation}`).join("\n") || "No rules"}\n\n## Control boundaries\n${notes.controls.join(", ") || "None marked"}\n\n## Working claim\n${notes.claim || "(not entered)"}\n\n## Falsifier\n${notes.falsifier || "(not entered)"}\n\n## Positive-service test\n${notes.positiveTest || "(not entered)"}\n\n## Remaining unknown\n${notes.unknown || "(not entered)"}\n\n## Revised claim\n${notes.challenge || "(not entered)"}\n`;
    const url = URL.createObjectURL(new Blob([body], { type: "text/markdown" }));
    const link = document.createElement("a"); link.href = url; link.download = "utility-ot-workbench-notes.md"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (!traffic || !scenario || !policy) { document.querySelector("main").textContent = "Local evidence files could not be loaded."; return; }
  loadState(); renderOverview(); renderAssets(); renderTraffic(); renderMap(); renderCandidate(); renderGroups(); renderRules(); renderSimulation(); renderAssurance(); loadNotes();
  byId("rule-source").innerHTML = groupOptions(); byId("rule-destination").innerHTML = groupOptions();
  renderGroupReadiness();
  document.querySelectorAll(".tabs button, [data-open]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.view || button.dataset.open)));
  byId("explore-toggle").addEventListener("click", () => {
    state.explore = !state.explore;
    if (state.explore) state.unlocked = views.length - 1;
    byId("workbench-views").hidden = !state.explore;
    byId("explore-toggle").textContent = state.explore ? "Return to guided" : "Explore freely";
    byId("explore-toggle").setAttribute("aria-expanded", String(state.explore));
    if (!state.explore) showView("overview");
    else showView(state.view);
  });
  byId("open-manifest").addEventListener("click", () => {
    state.manifestOpen = true; saveState();
    byId("asset-filter").value = "all";
    renderOverview(); renderAssets(); renderGroups(); renderMap();
  });
  byId("asset-search").addEventListener("input", renderAssets);
  byId("asset-filter").addEventListener("change", renderAssets);
  document.querySelectorAll("[data-map-mode]").forEach((button) => button.addEventListener("click", () => {
    state.mapMode = button.dataset.mapMode;
    document.querySelectorAll("[data-map-mode]").forEach((candidate) => candidate.classList.toggle("active", candidate === button));
    state.selectedFlow = ""; renderMap();
  }));
  byId("operation-filter").addEventListener("change", (event) => { state.operationFilter = event.target.value; renderMap(); });
  byId("mark-candidate").addEventListener("click", () => {
    const packet = Number(byId("candidate-packet").value);
    if (!requestEvents.some((event) => event.packet === packet)) return;
    state.selectedCandidate = packet; saveState(); renderCandidate();
  });
  byId("open-assurance").addEventListener("click", () => unlock("assurance"));
  byId("open-segmentation").addEventListener("click", () => unlock("segmentation"));
  byId("go-assign-groups").addEventListener("click", () => {
    showView("assets"); byId(state.manifestOpen ? "asset-group" : "open-manifest").focus();
  });
  byId("rule-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.rules.length >= 20 || byId("add-rule").disabled) return;
    state.rules.push({ id: `r${Date.now()}-${Math.random().toString(16).slice(2, 6)}`, source: byId("rule-source").value,
      destination: byId("rule-destination").value, operation: byId("rule-operation").value, action: byId("rule-action").value });
    byId("rule-form").reset(); saveState(); renderRules(); renderSimulation();
  });
  byId("open-challenge").addEventListener("click", () => unlock("challenge"));
  document.querySelectorAll("textarea, [data-control]").forEach((input) => input.addEventListener("input", saveNotes));
  byId("export-notes").addEventListener("click", downloadNotes);
  byId("reset-notes").addEventListener("click", () => {
    for (const id of ["claim", "falsifier", "positive-test", "unknown", "challenge"]) byId(id).value = "";
    document.querySelectorAll("[data-control]").forEach((input) => { input.checked = false; }); saveNotes();
  });
  showView(state.view);
})();
