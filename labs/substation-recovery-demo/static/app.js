'use strict';

const LAB_BASE = new URL(document.currentScript.src).pathname.replace(/\/app\.js$/, '');

const TESTS = {
  upstream_counterexample: {
    label: 'Upstream-close counterexample',
    purpose: 'Begin with the faulted branch positioned closed, then ask the active ST build to close B0.',
    steps: ['Reset with S3 closed and B0 open', 'Submit CLOSE B0', 'Evaluate compiled ST', 'Observe physics and protection']
  },
  legitimate_restore: {
    label: 'Legitimate healthy restoration',
    purpose: 'Close the healthy branches and B0, then require service to remain safe for 1000 ms.',
    steps: ['Reset all contacts open', 'Close S1 and S2', 'Close B0', 'Sustain healthy service for 1000 ms']
  },
  moved_fault: {
    label: 'Round 2: fault moved to S2',
    purpose: 'Move the out-of-service mask and test whether the interlock generalizes without target-specific logic.',
    steps: ['Move the fault to S2', 'Close healthy S1 and S3', 'Close B0', 'Check safety and service for 1000 ms']
  }
};

const PRESET_LABELS = {
  vulnerable: 'Vulnerable: present current only',
  target_local: 'Faulty patch: target only',
  deny_all: 'Faulty patch: deny every close',
  repaired: 'Repair: resulting topology'
};

const REFERENCE_PRESET = 'repaired';

const app = {
  snapshot: null,
  events: [],
  presets: {},
  selectedEvent: -1,
  followLive: true,
  latestSeq: 0,
  playing: false,
  playTimer: null,
  selectedDevice: 'B0',
  connected: false,
  dirtySource: false,
  activePreset: 'vulnerable',
  referenceRevealed: false,
  session: null,
  booted: false,
  polling: false
};

const $ = id => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(`${LAB_BASE}${path}`, {
    cache: 'no-store',
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    ...options
  });
  const payload = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/session/login') showLogin('Your session ended. Enter your access code to reconnect.');
    const error = new Error(payload.error || `HTTP ${response.status}`);
    error.payload = payload;
    throw error;
  }
  return payload;
}

function setConnection(connected, detail) {
  app.connected = connected;
  $('connection-label').textContent = connected ? 'Private live session:' : 'Disconnected:';
  $('connection-detail').textContent = detail;
  $('execution-badge').textContent = connected ? 'LIVE SIMULATION' : 'DISCONNECTED';
  $('execution-badge').classList.toggle('connected', connected);
  $('execution-badge').classList.toggle('disconnected', !connected);
}

function mergeSnapshot(snapshot, initial = false) {
  app.snapshot = snapshot;
  const existing = new Set(app.events.map(event => event.seq));
  for (const event of snapshot.events || []) {
    if (!existing.has(event.seq)) app.events.push(event);
  }
  app.events.sort((a, b) => a.seq - b.seq);
  app.latestSeq = Math.max(app.latestSeq, snapshot.latestSeq || 0);
  if (initial || app.followLive) app.selectedEvent = app.events.length - 1;
  if (snapshot.build && snapshot.build.preset && !app.dirtySource) {
    app.activePreset = snapshot.build.preset;
  }
  render();
}

function liveDisplayState() {
  if (!app.snapshot) return null;
  if (!app.followLive && app.selectedEvent >= 0 && app.events[app.selectedEvent]) return app.events[app.selectedEvent];
  return {
    eventId: 'live-state',
    seq: app.snapshot.latestSeq,
    simTimeMs: app.snapshot.simTimeMs,
    stage: app.snapshot.activeTest ? 'Regression running' : 'Live state',
    category: 'state',
    description: app.snapshot.activeTest
      ? `${app.snapshot.activeTest.testId} is running against ${app.snapshot.build.buildId}.`
      : 'The simulator is advancing on an independent 50 ms clock.',
    request: null,
    transport: app.snapshot.protocolMode,
    decision: 'NONE',
    reason: 'current backend state',
    buildId: app.snapshot.build.buildId,
    sourceSha256: app.snapshot.build.sourceSha256,
    positions: app.snapshot.positions,
    measurements: app.snapshot.measurements,
    service: app.snapshot.service,
    trip: app.snapshot.trip,
    oos: app.snapshot.oos,
    mission: app.snapshot.mission,
    runId: app.snapshot.runId,
    generation: app.snapshot.generation
  };
}

function setVerdict(id, value) {
  const el = $(id);
  const normalized = ['pass', 'fail', 'pending'].includes(value) ? value : 'na';
  el.textContent = normalized === 'na' ? 'N/A' : normalized[0].toUpperCase() + normalized.slice(1);
  el.className = `verdict ${normalized}`;
}

function updateMission(event) {
  const mission = event.mission || {};
  setVerdict('safety-verdict', mission.safety);
  setVerdict('protection-verdict', mission.protection);
  setVerdict('service-verdict', mission.requiredService);
  const target = mission.serviceTargetMs || 1000;
  setVerdict('duration-verdict', mission.serviceMs >= target ? 'pass' : 'pending');
  $('safety-detail').textContent = mission.safety === 'fail' ? `${event.oos} was energized during this run` : 'No prohibited section energized';
  $('protection-detail').textContent = event.trip ? 'Protective trip occurred' : 'No protective trip';
  const required = (app.snapshot && app.snapshot.requiredLoads) || (event.oos === 'S2' ? ['S1', 'S3'] : ['S1', 'S2']);
  $('service-detail').textContent = mission.requiredService === 'pass' ? `${required.join(' and ')} are served` : `${required.join(' and ')} must be served`;
  $('duration-detail').textContent = `${mission.serviceMs || 0} / ${target} ms`;
}

function updateContact(device, isClosed) {
  $(`contact-${device}`).classList.toggle('open', !isClosed);
  $(`label-${device}`).textContent = isClosed ? 'CLOSED' : 'OPEN';
}

function wireState(element, status) {
  element.classList.remove('live', 'fault', 'dead');
  element.classList.add(status);
}

function updateDiagram(event) {
  const positions = event.positions || { B0: false, S1: false, S2: false, S3: false };
  const measurements = event.measurements || { busV: 0, sourceA: 0, branches: { S1: 0, S2: 0, S3: 0 } };
  const service = event.service || { S1: false, S2: false, S3: false };
  ['B0', 'S1', 'S2', 'S3'].forEach(device => updateContact(device, Boolean(positions[device])));

  const liveBus = Boolean(positions.B0);
  wireState($('source-wire'), 'live');
  wireState($('b0-bus-wire'), liveBus ? 'live' : 'dead');
  wireState($('bus-wire'), liveBus ? 'live' : 'dead');

  ['S1', 'S2', 'S3'].forEach(device => {
    const isLive = liveBus && Boolean(positions[device]);
    const isFault = isLive && device === event.oos;
    wireState($(`wire-${device}`), isFault ? 'fault' : isLive ? 'live' : 'dead');
    wireState($(`load-wire-${device}`), isFault ? 'fault' : isLive ? 'live' : 'dead');
    const load = $(`load-${device}`);
    load.classList.toggle('served', Boolean(service[device]));
    load.classList.toggle('oos', device === event.oos);
    $(`title-${device}`).textContent = device === event.oos ? 'FAULTED' : `LOAD ${device.slice(1)}`;
    const suffix = device === event.oos ? 'OOS' : service[device] ? 'SERVED' : 'OFF';
    const current = $(`current-${device}`);
    current.textContent = `${Number(measurements.branches[device] || 0).toFixed(1)} A | ${suffix}`;
    current.classList.toggle('svg-danger', device === event.oos);
    current.classList.toggle('svg-good', Boolean(service[device]));
  });

  $('bus-voltage').textContent = `${Number(measurements.busV || 0).toFixed(1)} V | ${Number(measurements.sourceA || 0).toFixed(1)} A source`;
  const oosX = event.oos === 'S1' ? 260 : event.oos === 'S2' ? 450 : 640;
  $('oos-label').setAttribute('x', String(oosX));
  $('oos-label').textContent = `${event.oos} DECLARED OUT OF SERVICE`;
  document.querySelectorAll('[data-device]').forEach(node => {
    node.classList.toggle('oos', node.dataset.device === event.oos);
    node.classList.toggle('selected', node.dataset.device === app.selectedDevice);
  });
  document.querySelectorAll('[data-pick]').forEach(button => button.classList.toggle('active', button.dataset.pick === app.selectedDevice));

  const faultEnergized = Number(measurements.branches[event.oos] || 0) > 0.01;
  const station = $('station-state');
  station.textContent = event.trip ? 'Tripped' : faultEnergized ? 'Fault energized' : liveBus ? 'Energized' : 'Disconnected';
  station.className = `tag ${event.trip ? 'trip' : faultEnergized ? 'deny' : liveBus ? 'allow' : ''}`;
}

function renderMetadata(event) {
  if (!app.snapshot) return;
  $('run-id').textContent = app.snapshot.runId;
  $('scenario-id').textContent = app.snapshot.scenario;
  $('build-id').textContent = app.snapshot.build.buildId;
  $('execution-mode').textContent = app.snapshot.controllerMode;
  const requester = app.snapshot.activeTest ? 'Fixed test' : 'Manual';
  $('requester-mode').textContent = requester;
  $('requester-badge').textContent = requester.toUpperCase();
  $('sim-time').textContent = `${event.simTimeMs || 0} ms`;
  $('student-badge').textContent = app.session ? app.session.student.label.toUpperCase() : 'PRIVATE SESSION';
  $('event-kicker').textContent = event.stage;
  $('event-description').textContent = event.description;
  setConnection(true, `${app.snapshot.controllerMode}. ${app.snapshot.protocolMode}.`);
}

function renderEvidence(event) {
  const request = event.request ? `${event.request.action} ${event.request.device} (${event.request.authority})` : 'none';
  const positions = Object.entries(event.positions || {}).map(([key, value]) => `${key}:${value ? 'CLOSED' : 'OPEN'}`).join(' ');
  const values = [
    ['Event ID', event.eventId || 'live-state'],
    ['Simulation time', `${event.simTimeMs || 0} ms`],
    ['Stage', event.stage || 'Live state'],
    ['Request', request],
    ['Transport', event.transport || app.snapshot.protocolMode],
    ['ST decision', event.decision || 'NONE'],
    ['Decision reason', event.reason || 'current backend state'],
    ['Actual positions', positions],
    ['Bus / source', `${Number(event.measurements.busV || 0).toFixed(1)} V / ${Number(event.measurements.sourceA || 0).toFixed(1)} A`],
    ['Trip', event.trip ? 'ACTIVE' : 'clear'],
    ['Build', event.buildId || app.snapshot.build.buildId]
  ];
  const grid = $('evidence-grid');
  grid.replaceChildren();
  for (const [label, value] of values) {
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = value;
    grid.append(dt, dd);
  }

  const list = $('event-list');
  list.replaceChildren();
  for (const [index, item] of app.events.entries()) {
    const li = document.createElement('li');
    if (!app.followLive && index === app.selectedEvent) li.classList.add('current');
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-label', `Show ${item.stage} at ${item.simTimeMs} milliseconds`);
    button.addEventListener('click', () => selectEvent(index));
    const time = document.createElement('span');
    time.className = 'event-time';
    time.textContent = `${item.simTimeMs} ms`;
    const body = document.createElement('span');
    const stage = document.createElement('span');
    stage.className = 'event-stage';
    stage.textContent = item.stage;
    const br = document.createElement('br');
    const summary = document.createElement('span');
    summary.textContent = item.description;
    body.append(stage, br, summary);
    const tag = document.createElement('span');
    tag.className = `tag ${(item.decision || '').toLowerCase()}`;
    tag.textContent = item.decision || item.category;
    button.append(time, body, tag);
    li.append(button);
    list.append(li);
  }
}

function renderTimeline() {
  const track = $('timeline-track');
  track.replaceChildren();
  for (const [index, event] of app.events.entries()) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'timeline-event';
    if (!app.followLive && index < app.selectedEvent) button.classList.add('past');
    if ((!app.followLive && index === app.selectedEvent) || (app.followLive && index === app.events.length - 1)) button.classList.add('active');
    button.setAttribute('aria-label', `${event.stage}, ${event.simTimeMs} milliseconds`);
    const time = document.createElement('span');
    time.className = 'time';
    time.textContent = `${event.simTimeMs} ms`;
    const label = document.createElement('span');
    label.className = 'label';
    label.textContent = event.stage;
    button.append(time, label);
    button.addEventListener('click', () => selectEvent(index));
    track.append(button);
  }
  const position = app.followLive ? Math.max(0, app.events.length - 1) : Math.max(0, app.selectedEvent);
  $('scrubber').max = String(Math.max(0, app.events.length - 1));
  $('scrubber').value = String(position);
  $('timeline-position').textContent = app.followLive ? `LIVE | ${app.events.length} events` : `Event ${position + 1} of ${app.events.length}`;
  $('playback-time').textContent = `${liveDisplayState().simTimeMs || 0} ms`;
  const active = track.children[position];
  if (active) {
    const right = active.offsetLeft + active.offsetWidth;
    if (right > track.scrollLeft + track.clientWidth) track.scrollLeft = right - track.clientWidth;
    if (active.offsetLeft < track.scrollLeft) track.scrollLeft = active.offsetLeft;
  }
}

function renderTestSteps() {
  const test = TESTS[$('trace-select').value] || TESTS.upstream_counterexample;
  $('trace-purpose').textContent = test.purpose;
  const list = $('sequence-list');
  list.replaceChildren();
  test.steps.forEach((text, index) => {
    const li = document.createElement('li');
    const step = document.createElement('span');
    step.className = 'event-time';
    step.textContent = `Step ${index + 1}`;
    const body = document.createElement('span');
    body.textContent = text;
    const status = document.createElement('span');
    status.className = 'tag';
    status.textContent = app.snapshot && app.snapshot.activeTest && app.snapshot.activeTest.testId === $('trace-select').value ? 'running' : 'fixed';
    li.append(step, body, status);
    list.append(li);
  });
}

function renderSourceMeta() {
  if (!app.snapshot) return;
  $('source-id').value = app.dirtySource ? 'uncompiled draft' : app.snapshot.build.buildId;
  if (app.snapshot.lastTest) {
    const test = app.snapshot.lastTest;
    $('request-feedback').className = `feedback ${test.passed ? 'good' : 'error'}`;
    $('request-feedback').textContent = `${test.testId}: ${test.status.toUpperCase()} - ${test.detail} (${test.durationMs} ms wall time)`;
  } else if (app.snapshot.activeTest) {
    $('request-feedback').className = 'feedback';
    $('request-feedback').textContent = `${app.snapshot.activeTest.testId} is running against ${app.snapshot.activeTest.buildId}.`;
  }
}

function render() {
  if (!app.snapshot) return;
  const event = liveDisplayState();
  renderMetadata(event);
  updateMission(event);
  updateDiagram(event);
  renderEvidence(event);
  renderTimeline();
  renderTestSteps();
  renderSourceMeta();
  updateDraftPreview();
}

function selectEvent(index) {
  if (!app.events.length) return;
  app.followLive = false;
  app.selectedEvent = Math.max(0, Math.min(app.events.length - 1, index));
  render();
}

function followLive() {
  app.followLive = true;
  app.selectedEvent = app.events.length - 1;
  render();
}

function setTab(name) {
  ['requests', 'controller', 'evidence'].forEach(tab => {
    $(`tab-${tab}`).setAttribute('aria-selected', tab === name ? 'true' : 'false');
    $(`panel-${tab}`).classList.toggle('active', tab === name);
  });
}

function selectDevice(device) {
  app.selectedDevice = device;
  $('request-device').value = device;
  updateDraftPreview();
  render();
}

function updateDraftPreview() {
  if (!app.snapshot) return;
  const action = $('request-action').value;
  const device = $('request-device').value;
  $('draft-operation').textContent = `${action} ${device}`;
  $('draft-authority').textContent = action === 'OPEN' ? 'Human recovery' : 'Manual';
  $('draft-generation').textContent = String(app.snapshot.generation);
}

function simpleDiff(before, after) {
  const holder = $('source-diff');
  holder.replaceChildren();
  if (before === after) {
    const row = document.createElement('div');
    row.className = 'diff-line';
    const mark = document.createElement('span'); mark.textContent = ' ';
    const text = document.createElement('span'); text.textContent = 'No changes from the selected starting source.';
    row.append(mark, text); holder.append(row); return;
  }
  for (const line of before.split('\n')) {
    const row = document.createElement('div'); row.className = 'diff-line remove';
    const mark = document.createElement('span'); mark.textContent = '-';
    const text = document.createElement('span'); text.textContent = line;
    row.append(mark, text); holder.append(row);
  }
  for (const line of after.split('\n')) {
    const row = document.createElement('div'); row.className = 'diff-line add';
    const mark = document.createElement('span'); mark.textContent = '+';
    const text = document.createElement('span'); text.textContent = line;
    row.append(mark, text); holder.append(row);
  }
}

function loadPreset(name) {
  if (!app.presets[name]) return;
  app.activePreset = name;
  app.dirtySource = false;
  $('source-preset').value = name;
  $('st-source').value = app.presets[name];
  $('source-id').value = app.snapshot ? app.snapshot.build.buildId : 'not compiled';
  $('compile-feedback').className = 'feedback';
  $('compile-feedback').textContent = 'Starting source loaded. Compile it to create and activate a native controller build.';
  simpleDiff(app.presets[name], app.presets[name]);
}

function addPresetOption(name) {
  if (!app.presets[name] || $('source-preset').querySelector(`option[value="${name}"]`)) return;
  const option = document.createElement('option');
  option.value = name;
  option.textContent = PRESET_LABELS[name] || name;
  $('source-preset').append(option);
}

function revealReference() {
  const confirmed = window.confirm(
    'Reveal the reference build only after you have committed to a repair and two tests. Continue?'
  );
  if (!confirmed) return;
  app.referenceRevealed = true;
  addPresetOption(REFERENCE_PRESET);
  loadPreset(REFERENCE_PRESET);
  $('reference-reveal').open = false;
  $('compile-feedback').textContent = 'Reference source loaded but not active. Compile it before running the regression tests.';
}

async function sendCommand() {
  const action = $('request-action').value;
  const device = $('request-device').value;
  const authority = action === 'OPEN' ? 'human-recovery' : 'manual';
  $('request-feedback').className = 'feedback';
  $('request-feedback').textContent = `Submitting ${action} ${device}...`;
  try {
    const result = await api('/api/commands', {
      method: 'POST',
      body: JSON.stringify({ action, device, authority })
    });
    followLive();
    $('request-feedback').className = 'feedback good';
    $('request-feedback').textContent = `${result.commandId} entered the live command queue.`;
  } catch (error) {
    $('request-feedback').className = 'feedback error';
    $('request-feedback').textContent = error.message;
  }
}

async function runRegression() {
  const testId = $('trace-select').value;
  $('request-feedback').className = 'feedback';
  $('request-feedback').textContent = `Starting ${TESTS[testId].label}...`;
  try {
    const result = await api('/api/tests/run', { method: 'POST', body: JSON.stringify({ testId }) });
    app.events = [];
    app.latestSeq = 0;
    app.followLive = true;
    $('request-feedback').textContent = `${result.testRunId} started against ${result.buildId}.`;
  } catch (error) {
    $('request-feedback').className = 'feedback error';
    $('request-feedback').textContent = error.message;
  }
}

async function compileSource() {
  const source = $('st-source').value;
  $('compile-draft').disabled = true;
  $('compile-feedback').className = 'feedback';
  $('compile-feedback').textContent = 'Compiling Structured Text with matiec...';
  try {
    const result = await api('/api/builds/compile', { method: 'POST', body: JSON.stringify({ source }) });
    app.dirtySource = false;
    $('source-id').value = result.buildId;
    $('compile-feedback').className = 'feedback good';
    $('compile-feedback').textContent = `Compile clean. ${result.buildId} is active; source SHA-256 ${result.sourceSha256.slice(0, 16)}...`;
    followLive();
  } catch (error) {
    const diagnostics = error.payload && error.payload.diagnostics ? ` ${error.payload.diagnostics}` : '';
    $('compile-feedback').className = 'feedback error';
    $('compile-feedback').textContent = `${error.message}.${diagnostics}`.slice(0, 1200);
  } finally {
    $('compile-draft').disabled = false;
  }
}

async function resetRun() {
  if (app.snapshot && app.snapshot.activeTest) return;
  try {
    const scenario = $('trace-select').value === 'moved_fault' ? 's2_fault' : 's3_fault';
    const snapshot = await api('/api/reset', { method: 'POST', body: JSON.stringify({ scenario }) });
    app.events = [];
    app.latestSeq = 0;
    app.followLive = true;
    mergeSnapshot(snapshot, true);
  } catch (error) {
    $('request-feedback').className = 'feedback error';
    $('request-feedback').textContent = error.message;
  }
}

function exportEvidence() {
  if (!app.snapshot) return;
  const payload = { ...app.snapshot, events: app.events, exportedAt: new Date().toISOString() };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${app.snapshot.runId}-live-evidence.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function togglePlayback() {
  if (app.playing) {
    app.playing = false;
    clearInterval(app.playTimer);
    app.playTimer = null;
    $('play-events').textContent = '\u25b6';
    return;
  }
  if (!app.events.length) return;
  app.followLive = false;
  if (app.selectedEvent >= app.events.length - 1) app.selectedEvent = 0;
  app.playing = true;
  $('play-events').textContent = '\u275a\u275a';
  app.playTimer = setInterval(() => {
    if (app.selectedEvent >= app.events.length - 1) {
      app.playing = false;
      clearInterval(app.playTimer);
      app.playTimer = null;
      $('play-events').textContent = '\u25b6';
      return;
    }
    app.selectedEvent += 1;
    render();
  }, 800);
  render();
}

async function poll() {
  app.polling = true;
  while (app.polling) {
    try {
      const snapshot = await api(`/api/state?after=${app.latestSeq}&wait=10`);
      mergeSnapshot(snapshot, false);
    } catch (error) {
      setConnection(false, `${error.message}. Retrying the local service.`);
      if (!app.session) break;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}

async function initializeLab() {
  if (app.booted) return;
  app.booted = true;
  Object.entries(TESTS).forEach(([id, test]) => {
    const option = document.createElement('option');
    option.value = id;
    option.textContent = test.label;
    $('trace-select').append(option);
  });
  $('trace-select').value = 'upstream_counterexample';

  const presets = await api('/api/presets');
  for (const preset of presets.presets) {
    app.presets[preset.id] = preset.source;
    if (preset.id !== REFERENCE_PRESET) addPresetOption(preset.id);
  }

  const snapshot = await api('/api/state');
  mergeSnapshot(snapshot, true);
  const workspace = presets.workspace || {};
  app.activePreset = workspace.activePreset || 'vulnerable';
  if (app.activePreset === REFERENCE_PRESET) {
    app.referenceRevealed = true;
    addPresetOption(REFERENCE_PRESET);
  }
  app.dirtySource = false;
  $('source-preset').value = app.activePreset;
  $('st-source').value = workspace.activeSource || app.presets[app.activePreset];
  $('source-id').value = workspace.activeBuildId || snapshot.build.buildId;
  $('compile-feedback').className = 'feedback good';
  $('compile-feedback').textContent = 'Your saved controller workspace is active.';
  simpleDiff(app.presets.vulnerable || '', $('st-source').value);

  ['requests', 'controller', 'evidence'].forEach(tab => $('tab-' + tab).addEventListener('click', () => setTab(tab)));
  document.querySelectorAll('[data-pick]').forEach(button => button.addEventListener('click', () => selectDevice(button.dataset.pick)));
  document.querySelectorAll('[data-device]').forEach(node => {
    node.addEventListener('click', () => selectDevice(node.dataset.device));
    node.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectDevice(node.dataset.device);
      }
    });
  });

  $('trace-select').addEventListener('change', renderTestSteps);
  $('request-device').addEventListener('change', event => selectDevice(event.target.value));
  $('request-action').addEventListener('change', updateDraftPreview);
  $('prepare-request').addEventListener('click', sendCommand);
  $('jump-request-event').addEventListener('click', runRegression);
  $('source-preset').addEventListener('change', event => loadPreset(event.target.value));
  $('st-source').addEventListener('input', () => {
    app.dirtySource = true;
    $('source-id').value = 'uncompiled draft';
    $('compile-feedback').className = 'feedback';
    $('compile-feedback').textContent = 'Source changed. The active controller build is unchanged until compilation succeeds.';
    simpleDiff(app.presets[app.activePreset] || '', $('st-source').value);
  });
  $('compile-draft').addEventListener('click', compileSource);
  $('restore-source').addEventListener('click', () => loadPreset(app.activePreset));
  $('compile-error').addEventListener('click', () => {
    const current = $('st-source').value;
    $('st-source').value = current.replace(/END_FUNCTION\s*$/i, 'CloseInterlock := ;\nEND_FUNCTION');
    $('st-source').dispatchEvent(new Event('input'));
  });
  $('load-reference').addEventListener('click', revealReference);
  $('previous-event').addEventListener('click', () => selectEvent(Math.max(0, app.selectedEvent - 1)));
  $('next-event').addEventListener('click', () => {
    if (app.selectedEvent >= app.events.length - 1) followLive();
    else selectEvent(app.selectedEvent + 1);
  });
  $('play-events').addEventListener('click', togglePlayback);
  $('reset-events').addEventListener('click', resetRun);
  $('scrubber').addEventListener('input', event => selectEvent(Number(event.target.value)));
  $('export-evidence').addEventListener('click', exportEvidence);
  $('sign-out').addEventListener('click', logout);
  poll();
}

function showLogin(message = '') {
  app.polling = false;
  app.session = null;
  $('lab-shell').hidden = true;
  $('access-gate').hidden = false;
  $('access-feedback').textContent = message;
  $('access-submit').disabled = false;
}

async function login(event) {
  event.preventDefault();
  const accessCode = $('access-code').value.trim();
  $('access-submit').disabled = true;
  $('access-feedback').textContent = 'Opening your private lab...';
  try {
    const session = await api('/api/session/login', {
      method: 'POST',
      body: JSON.stringify({ accessCode })
    });
    app.session = session;
    $('access-code').value = '';
    $('access-gate').hidden = true;
    $('lab-shell').hidden = false;
    await initializeLab();
  } catch (error) {
    showLogin(error.message);
    $('access-code').focus();
  }
}

async function logout() {
  app.polling = false;
  try {
    await api('/api/session/logout', { method: 'POST', body: '{}' });
  } catch (_error) {
    // The browser still clears its local view if the service is unavailable.
  }
  window.location.reload();
}

async function bootstrap() {
  $('access-form').addEventListener('submit', login);
  const session = await api('/api/session');
  if (!session.authenticated) {
    showLogin();
    $('access-code').focus();
    return;
  }
  app.session = session;
  $('access-gate').hidden = true;
  $('lab-shell').hidden = false;
  await initializeLab();
}

bootstrap().catch(error => showLogin(error.message));
