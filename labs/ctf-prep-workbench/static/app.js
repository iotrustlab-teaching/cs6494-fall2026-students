(() => {
  "use strict";
  const traffic = window.WORKBENCH_TRAFFIC;
  const scenario = window.WORKBENCH_SCENARIO;
  const policy = window.WORKBENCH_POLICY;
  const views = ["overview", "assets", "communications", "segmentation", "assurance", "challenge"];
  const byId = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
  const observedIps = new Set(traffic.events.flatMap((event) => [event.source, event.destination]));
  const observed = scenario.assets.filter((asset) => observedIps.has(asset.ip));
  const leads = scenario.assets.filter((asset) => !observedIps.has(asset.ip));
  const requestEvents = traffic.events.filter((event) => event.direction === "request");
  const storageKey = "utilityOtWorkbenchStateV1";
  const noteKey = "utilityOtWorkbenchNotesV1";
  const state = {
    view: "overview", unlocked: 2, manifestOpen: false, selectedAsset: observed[0].ip,
    selectedFlow: "192.0.2.11|192.0.2.20", mapMode: "assets", operationFilter: "all",
    groups: Object.fromEntries(scenario.assets.map((asset) => [asset.ip, asset.group])),
    criticality: {}, rules: [], selectedCase: "baseline"
  };

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      if (saved.groups && typeof saved.groups === "object") {
        for (const asset of scenario.assets) if (policy.GROUPS.includes(saved.groups[asset.ip])) state.groups[asset.ip] = saved.groups[asset.ip];
      }
      if (saved.criticality && typeof saved.criticality === "object") state.criticality = saved.criticality;
      if (Array.isArray(saved.rules)) state.rules = saved.rules.filter((rule) =>
        rule && typeof rule.id === "string" && ["allow", "deny"].includes(rule.action) &&
        ["any", "write", "read"].includes(rule.operation) &&
        ["Any", ...policy.GROUPS].includes(rule.source) && ["Any", ...policy.GROUPS].includes(rule.destination)
      ).slice(0, 20);
    } catch (_) { /* Browser storage can be unavailable. */ }
  }
  function saveState() {
    try { localStorage.setItem(storageKey, JSON.stringify({ groups: state.groups, criticality: state.criticality, rules: state.rules })); } catch (_) { /* Local only. */ }
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

  function renderOverview() {
    byId("metric-observed").textContent = observed.length;
    byId("metric-leads").textContent = leads.length;
    byId("metric-writes").textContent = requestEvents.filter((event) => policy.operation(event) === "write").length;
    byId("site-layout").hidden = !state.manifestOpen;
    byId("utility-chain").innerHTML = scenario.areas.map((area, index) => `
      <div class="chain-stage ${state.manifestOpen && area === "Transfer skid" ? "chain-focus" : ""}">
        <small>AREA ${String(index + 1).padStart(2, "0")}</small><b>${state.manifestOpen ? esc(area) : "Unverified area"}</b>
        <span>${state.manifestOpen && area === "Transfer skid" ? "process context available" : "site record not validated"}</span>
      </div>${index < scenario.areas.length - 1 ? '<span class="chain-arrow">→</span>' : ""}`).join("");
    byId("map-status").textContent = state.manifestOpen ? "Site-record layout opened · only transfer-skid traffic observed" : "Site layout withheld · packet evidence covers one unknown cell";
  }

  function visibleAssets() { return state.manifestOpen ? scenario.assets : observed; }
  function renderAssets() {
    const query = byId("asset-search").value.trim().toLowerCase();
    const showAll = state.manifestOpen && byId("asset-filter").value === "all";
    const records = (showAll ? scenario.assets : observed).filter((asset) =>
      [asset.id, asset.ip, asset.name, asset.role].some((value) => value.toLowerCase().includes(query))
    );
    byId("asset-filter").querySelector('option[value="all"]').disabled = !state.manifestOpen;
    byId("asset-rows").innerHTML = records.map((asset) => {
      const events = eventsFor(asset);
      return `<tr class="asset-row ${state.selectedAsset === asset.ip ? "selected" : ""}" tabindex="0" data-ip="${esc(asset.ip)}">
        <td><b>${state.manifestOpen ? esc(asset.id) : "unresolved"}</b><small>${state.manifestOpen ? esc(asset.name) : "Packet endpoint"}</small></td>
        <td><code>${esc(asset.ip)}</code><small>${macFor(asset) || "MAC not observed"}</small></td>
        <td>${state.manifestOpen ? esc(asset.role) : (events.some((event) => event.port === 502 && event.direction === "request") ? "Modbus server candidate" : "Modbus client candidate")}</td>
        <td><span class="badge ${isObserved(asset) ? "observed" : "supplied"}">${isObserved(asset) ? "Packet" : "Site record"}</span></td>
        <td>${state.manifestOpen ? esc(state.groups[asset.ip]) : "Unassigned"}</td><td>${esc(state.criticality[asset.ip] || "Unassessed")}</td></tr>`;
    }).join("") || '<tr><td colspan="6">No assets match this filter.</td></tr>';
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
        <dt>Peers</dt><dd>${peers.length ? peers.map(esc).join(", ") : "None observed"}</dd><dt>Packets</dt><dd>${events.map((event) => `#${event.packet}`).join(", ") || "None"}</dd></dl></div>
      <div class="sheet-block"><span class="sheet-label supplied-text">SUPPLIED SITE RECORD</span>
        <p>${state.manifestOpen ? `${esc(asset.name)} · ${esc(asset.role)} · ${esc(asset.area)}` : "Open the site record to compare names and roles with packet evidence."}</p></div>
      <div class="sheet-block"><span class="sheet-label">UNKNOWN / STUDENT ASSESSMENT</span>
        <p>Vendor, model, firmware, exact program and physical authority are not established by these packets.</p>
        <label>Proposed asset group<select id="asset-group" ${state.manifestOpen ? "" : "disabled"}>${groupOptions}</select></label>
        <label>Process criticality<select id="asset-criticality">${criticalityOptions}</select></label></div>`;
    byId("asset-group").addEventListener("change", (event) => { state.groups[asset.ip] = event.target.value; saveState(); renderAssets(); renderGroups(); renderMap(); renderSimulation(); });
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
      const source = state.manifestOpen ? state.groups[flow.source] : "Unassigned";
      const destination = state.manifestOpen ? state.groups[flow.destination] : "Unassigned";
      const key = `${source}|${destination}`;
      if (!grouped.has(key)) grouped.set(key, { source, destination, key, packets: [] });
      grouped.get(key).packets.push(...filteredFlowPackets(flow));
    });
    return [...grouped.values()];
  }
  function renderMap() {
    const flows = mapFlows();
    const groupMode = state.mapMode === "groups";
    const svg = byId("flow-map");
    const coords = flows.map((flow, index) => ({ ...flow, y: 75 + index * 150 }));
    const text = (value) => esc(value);
    svg.innerHTML = `<defs><marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10Z" fill="#c8663c"/></marker></defs>
      <rect x="610" y="120" width="248" height="105" rx="4" class="map-dest"/><text x="628" y="159" class="node-label">${groupMode ? text(state.manifestOpen ? state.groups["192.0.2.20"] : "Unassigned") : "192.0.2.20"}</text><text x="628" y="187" class="node-sub">${groupMode ? "group / controller endpoint" : (state.manifestOpen ? "Transfer controller" : "Modbus server candidate")}</text>
      ${coords.map((flow) => `<g data-flow="${esc(flow.key)}" class="map-flow" tabindex="0" role="button" aria-label="Inspect ${text(flow.source)} to ${text(flow.destination)} flow">
        <rect x="42" y="${flow.y - 28}" width="250" height="85" rx="4" class="map-source"/><text x="60" y="${flow.y + 5}" class="node-label">${text(flow.source)}</text><text x="60" y="${flow.y + 32}" class="node-sub">${groupMode ? "asset group" : (state.manifestOpen ? text(scenario.assets.find((asset) => asset.ip === flow.source)?.name) : "packet endpoint")}</text>
        <path d="M292 ${flow.y + 13} L610 172" class="map-line" marker-end="url(#flow-arrow)"/><text x="365" y="${flow.y - 7}" class="edge-label">Modbus/TCP · ${flow.packets.length} packets</text></g>`).join("")}
      ${!flows.length ? '<text x="75" y="165" class="empty-map">No flows match this operation filter.</text>' : ""}`;
    svg.querySelectorAll("[data-flow]").forEach((node) => {
      const select = () => { state.selectedFlow = node.dataset.flow; renderMap(); };
      node.addEventListener("click", select);
      node.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } });
      node.classList.toggle("selected", node.dataset.flow === state.selectedFlow);
    });
    const selected = flows.find((flow) => flow.key === state.selectedFlow) || flows[0];
    if (selected) state.selectedFlow = selected.key;
    byId("edge-detail").innerHTML = selected ? `<div class="edge-summary"><b>${text(selected.source)} → ${text(selected.destination)}</b><p>${selected.packets.length} observed packets · Modbus/TCP</p><p>Direction and counts from PCAP. Names and groups are student/supplied context.</p></div>
      <div class="edge-packets">${selected.packets.map((event) => `<div><b>#${event.packet}</b><span>${text(operationLabel(event))}${event.address !== null ? ` · reg ${event.address}` : ""}${packetValue(event) !== "—" ? ` · value ${text(packetValue(event))}` : ""}</span></div>`).join("")}</div>` : '<p class="surface-note">No captured packets match this filter.</p>';
  }
  function renderTraffic() {
    byId("traffic-rows").innerHTML = traffic.events.map((event) => `<tr><td>#${event.packet}</td><td>${event.seconds.toFixed(2)}</td>
      <td><code>${esc(event.source)} → ${esc(event.destination)}</code></td><td class="${event.function === 6 ? "write-op" : ""}">${esc(operationLabel(event))}</td>
      <td>${event.address ?? "—"}</td><td>${esc(packetValue(event))}</td></tr>`).join("");
  }

  function groupOptions() { return ["Any", ...policy.GROUPS].map((group) => `<option value="${esc(group)}">${esc(group)}</option>`).join(""); }
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
      return `<tr><td><b>${esc(event.origin)}</b></td><td>${esc(outcome.source)} → ${esc(outcome.destination)}</td>
        <td>${esc(outcome.operation)} · reg ${event.address ?? "?"}</td><td><span class="badge ${outcome.action === "deny" ? "denied" : "allowed"}">${esc(outcome.action)}</span></td><td>${esc(outcome.rule)}</td></tr>`;
    }).join("");
  }

  function timeline(steps) {
    return steps.map(([time, source, description]) => `<div class="event"><time>${esc(time)}</time><b>${esc(source)}</b><span>${esc(description)}</span></div>`).join("");
  }
  function renderCase(id) {
    const selected = scenario.cases.find((item) => item.id === id && id !== "stale") || scenario.cases[0];
    state.selectedCase = selected.id;
    byId("case-picker").querySelectorAll("button").forEach((button) => button.classList.toggle("active", button.dataset.case === selected.id));
    byId("case-summary").innerHTML = `<div class="case-body"><b>${esc(selected.label)}</b><p><strong>Initial state</strong> ${esc(selected.condition)}</p>
      <p><strong>Request</strong> ${esc(selected.command)}</p><p><strong>Decision</strong> ${esc(selected.decision)}</p>
      <p><strong>Reported</strong> ${esc(selected.feedback)}</p><p><strong>Physical</strong> ${esc(selected.physical)}</p>
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
    return { claim: byId("claim").value, challenge: byId("challenge").value,
      controls: [...document.querySelectorAll("[data-control]:checked")].map((input) => input.dataset.control) };
  }
  function loadNotes() {
    try {
      const notes = JSON.parse(localStorage.getItem(noteKey) || "{}");
      byId("claim").value = notes.claim || ""; byId("challenge").value = notes.challenge || "";
      document.querySelectorAll("[data-control]").forEach((input) => { input.checked = (notes.controls || []).includes(input.dataset.control); });
    } catch (_) { /* Export still works without storage. */ }
  }
  function saveNotes() { try { localStorage.setItem(noteKey, JSON.stringify(noteData())); } catch (_) { /* Local only. */ } }
  function downloadNotes() {
    const notes = noteData();
    const body = `# Utility OT Security Workbench notes\n\nFixture: Riverbend Water Utility (fictional)\n\n## Proposed asset groups\n${scenario.assets.map((asset) => `- ${asset.id}: ${state.groups[asset.ip]} (${isObserved(asset) ? "packet endpoint" : "site record only"})`).join("\n")}\n\n## Process criticality assessment\n${scenario.assets.map((asset) => `- ${asset.id}: ${state.criticality[asset.ip] || "Unassessed"}`).join("\n")}\n\n## Proposed network rules\n${state.rules.map((rule) => `- ${rule.action} ${rule.source} -> ${rule.destination} ${rule.operation}`).join("\n") || "No rules"}\n\n## Control boundaries\n${notes.controls.join(", ") || "None marked"}\n\n## Bounded claim\n${notes.claim || "(not entered)"}\n\n## Revised claim\n${notes.challenge || "(not entered)"}\n`;
    const url = URL.createObjectURL(new Blob([body], { type: "text/markdown" }));
    const link = document.createElement("a"); link.href = url; link.download = "utility-ot-workbench-notes.md"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (!traffic || !scenario || !policy) { document.querySelector("main").textContent = "Local evidence files could not be loaded."; return; }
  loadState(); renderOverview(); renderAssets(); renderTraffic(); renderMap(); renderGroups(); renderRules(); renderSimulation(); renderAssurance(); loadNotes();
  byId("rule-source").innerHTML = groupOptions(); byId("rule-destination").innerHTML = groupOptions();
  byId("rule-source").value = "Supervisory"; byId("rule-destination").value = "Control";
  document.querySelectorAll(".tabs button, [data-open]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.view || button.dataset.open)));
  byId("open-manifest").addEventListener("click", () => {
    state.manifestOpen = true; state.unlocked = Math.max(state.unlocked, 3);
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
  byId("open-segmentation").addEventListener("click", () => {
    if (!state.manifestOpen) { showView("assets"); return; }
    unlock("segmentation");
  });
  byId("rule-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.rules.length >= 20) return;
    state.rules.push({ id: `r${Date.now()}-${Math.random().toString(16).slice(2, 6)}`, source: byId("rule-source").value,
      destination: byId("rule-destination").value, operation: byId("rule-operation").value, action: byId("rule-action").value });
    saveState(); renderRules(); renderSimulation();
  });
  byId("open-assurance").addEventListener("click", () => unlock("assurance"));
  byId("open-challenge").addEventListener("click", () => unlock("challenge"));
  document.querySelectorAll("textarea, [data-control]").forEach((input) => input.addEventListener("input", saveNotes));
  byId("export-notes").addEventListener("click", downloadNotes);
  byId("reset-notes").addEventListener("click", () => {
    byId("claim").value = ""; byId("challenge").value = "";
    document.querySelectorAll("[data-control]").forEach((input) => { input.checked = false; }); saveNotes();
  });
  showView("overview");
})();
