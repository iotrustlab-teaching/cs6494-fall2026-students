(() => {
  "use strict";
  const traffic = window.WORKBENCH_TRAFFIC;
  const scenario = window.WORKBENCH_SCENARIO;
  const views = ["visibility", "controller", "process", "controls"];
  const state = { unlocked: 0, view: "visibility", selectedPacket: 5, selectedCase: "baseline" };
  const byId = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);

  function operation(event) {
    if (event.function === 6) return event.direction === "request" ? "Write start request" : "Write acknowledged";
    return event.direction === "request" ? "Read holding register" : "Read response";
  }

  function packetValue(event) {
    if (event.value !== null) return String(event.value);
    if (event.function === 6 && event.data) return String(parseInt(event.data, 16));
    return "—";
  }

  function showPacket(number) {
    state.selectedPacket = number;
    const event = traffic.events.find((item) => item.packet === number);
    if (!event) return;
    byId("packet-id").textContent = `#${number}`;
    byId("packet-detail").innerHTML = [
      ["Timestamp", `+${event.seconds.toFixed(2)} s`], ["Source", event.source],
      ["Destination", event.destination], ["Protocol", "Modbus/TCP"],
      ["Function", `${event.function} · ${operation(event)}`],
      ["Register", event.address === null ? "Not in response PDU" : event.address],
      ["Value", packetValue(event)], ["Boundary", "Packet only; not physical feedback"]
    ].map(([term, value]) => `<dt>${escapeHtml(term)}</dt><dd>${escapeHtml(value)}</dd>`).join("");
    document.querySelectorAll(".packet-row").forEach((row) => {
      row.classList.toggle("selected", Number(row.dataset.packet) === number);
    });
  }

  function renderTraffic() {
    byId("asset-list").innerHTML = scenario.assets.map((asset) => `
      <div class="asset"><strong>${escapeHtml(asset.name)}</strong><code>${escapeHtml(asset.ip)}</code><small>${escapeHtml(asset.role)}</small></div>`).join("");
    byId("traffic-rows").innerHTML = traffic.events.map((event) => `
      <tr class="packet-row" tabindex="0" data-packet="${event.packet}" aria-label="Packet ${event.packet}, ${escapeHtml(operation(event))}">
        <td>${event.seconds.toFixed(2)}</td><td>${escapeHtml(event.source)} → ${escapeHtml(event.destination)}</td>
        <td class="${event.function === 6 ? "write-op" : ""}">${escapeHtml(operation(event))}</td>
        <td>${event.address ?? "—"}</td><td>${escapeHtml(packetValue(event))}</td></tr>`).join("");
    document.querySelectorAll(".packet-row").forEach((row) => {
      const select = () => showPacket(Number(row.dataset.packet));
      row.addEventListener("click", select);
      row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } });
    });
    showPacket(state.selectedPacket);
  }

  function timeline(steps) {
    return steps.map(([time, source, description]) => `<div class="event"><time>${escapeHtml(time)}</time><b>${escapeHtml(source)}</b><span>${escapeHtml(description)}</span></div>`).join("");
  }

  function renderController() {
    byId("st-source").textContent = scenario.source;
    byId("register-rows").innerHTML = scenario.registers.map((item) => `<tr><td>${item.address}</td><td>${escapeHtml(item.label)}</td><td>${escapeHtml(item.source)}</td></tr>`).join("");
    byId("baseline-timeline").innerHTML = timeline(scenario.cases[0].steps);
  }

  function showCase(id) {
    const selected = scenario.cases.find((item) => item.id === id);
    if (!selected) return;
    state.selectedCase = id;
    document.querySelectorAll("#case-picker button").forEach((button) => button.classList.toggle("active", button.dataset.case === id));
    byId("case-summary").innerHTML = `<strong>${escapeHtml(selected.label)}</strong>
      <p><b>Initial state:</b> ${escapeHtml(selected.condition)}</p>
      <p><b>Request:</b> ${escapeHtml(selected.command)}</p>
      <p><b>Controller decision:</b> ${escapeHtml(selected.decision)}</p>
      <p><b>Reported feedback:</b> ${escapeHtml(selected.feedback)}</p>
      <p><b>Physical outcome:</b> ${escapeHtml(selected.physical)}</p>
      <div class="case-outcomes"><span class="outcome ${selected.safety === "Preserved" ? "good" : "bad"}">Safety: ${escapeHtml(selected.safety)}</span>
      <span class="outcome ${selected.service === "Delivered" ? "good" : "neutral"}">Service: ${escapeHtml(selected.service)}</span></div>`;
    byId("case-timeline").innerHTML = timeline(selected.steps);
  }

  function renderCases() {
    byId("case-picker").innerHTML = scenario.cases.map((item) => `<button type="button" data-case="${escapeHtml(item.id)}" class="${item.id === state.selectedCase ? "active" : ""}">${escapeHtml(item.label)}</button>`).join("");
    document.querySelectorAll("#case-picker button").forEach((button) => button.addEventListener("click", () => showCase(button.dataset.case)));
    showCase(state.selectedCase);
  }

  function showView(view) {
    const index = views.indexOf(view);
    if (index < 0 || index > state.unlocked) return;
    state.view = view;
    document.querySelectorAll(".view").forEach((section) => section.classList.toggle("active", section.id === `view-${view}`));
    document.querySelectorAll(".tab").forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle("active", active);
      button.disabled = views.indexOf(button.dataset.view) > state.unlocked;
      if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
    });
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function unlock(view) {
    state.unlocked = Math.max(state.unlocked, views.indexOf(view));
    showView(view);
  }

  function loadNotes() {
    try {
      const notes = JSON.parse(localStorage.getItem("ctfPrepNotes") || "{}");
      byId("claim").value = notes.claim || "";
      byId("challenge").value = notes.challenge || "";
      document.querySelectorAll("[data-control]").forEach((input) => { input.checked = (notes.controls || []).includes(input.dataset.control); });
    } catch (_) { /* Private-browsing storage may be unavailable. */ }
  }

  function noteData() {
    return {
      claim: byId("claim").value, challenge: byId("challenge").value,
      controls: [...document.querySelectorAll("[data-control]:checked")].map((input) => input.dataset.control)
    };
  }

  function saveNotes() {
    try { localStorage.setItem("ctfPrepNotes", JSON.stringify(noteData())); } catch (_) { /* Export still works. */ }
  }

  function exportNotes() {
    const notes = noteData();
    const body = `# CTF Prep Workbench notes\n\nFixture: Transfer skid 04 (synthetic)\nSelected controls: ${notes.controls.join(", ") || "None marked"}\n\n## Bounded claim\n${notes.claim || "(not entered)"}\n\n## Changed assumption\n${notes.challenge || "(not entered)"}\n`;
    const url = URL.createObjectURL(new Blob([body], { type: "text/markdown" }));
    const link = document.createElement("a");
    link.href = url; link.download = "ctf-prep-notes.md"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (!traffic || !scenario) {
    document.querySelector("main").textContent = "The local evidence files could not be loaded.";
    return;
  }
  renderTraffic(); renderController(); renderCases(); loadNotes();
  document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));
  byId("reveal-controller").addEventListener("click", () => unlock("controller"));
  byId("reveal-process").addEventListener("click", () => unlock("process"));
  byId("reveal-controls").addEventListener("click", () => unlock("controls"));
  document.querySelectorAll("textarea, [data-control]").forEach((input) => input.addEventListener("input", saveNotes));
  byId("export-notes").addEventListener("click", exportNotes);
  byId("reset-notes").addEventListener("click", () => {
    byId("claim").value = ""; byId("challenge").value = "";
    document.querySelectorAll("[data-control]").forEach((input) => { input.checked = false; });
    saveNotes();
  });
})();
