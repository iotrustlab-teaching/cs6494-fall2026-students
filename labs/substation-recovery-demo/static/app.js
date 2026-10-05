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

const SUBMISSION_VERSION = 1;
const SUBMISSION_STEPS = {
  property: ['property-prohibited', 'property-service', 'property-source', 'property-boundary'],
  counterexample: ['counter-initial', 'counter-request', 'counter-decision', 'counter-effect', 'counter-omission'],
  repair: ['repair-explanation'],
  tests: [
    'test-prohibited-expected', 'test-prohibited-status', 'test-prohibited-observed', 'test-prohibited-reference',
    'test-legitimate-expected', 'test-legitimate-status', 'test-legitimate-observed', 'test-legitimate-reference'
  ],
  stress: ['stress-assumption', 'stress-evidence', 'stress-recheck', 'stress-positive'],
  transfer: [
    'transfer-context', 'transfer-property', 'transfer-missing', 'transfer-enforcement', 'transfer-assumption',
    'claim-assumptions', 'claim-evidence', 'claim-supports', 'claim-limits'
  ]
};
const SUBMISSION_PAGE_ORDER = [...Object.keys(SUBMISSION_STEPS), 'review'];
const SUBMISSION_PAGE_TITLES = {
  property: 'Property and boundary',
  counterexample: 'Counterexample',
  repair: 'Repair',
  tests: 'Two tests',
  stress: 'Assumption stress test',
  transfer: 'Transfer and bounded claim',
  review: 'Review and submit'
};
const SUBMISSION_IDENTITY_FIELDS = ['student-name', 'student-unid'];
const SUBMISSION_FIELD_IDS = SUBMISSION_IDENTITY_FIELDS.concat(...Object.values(SUBMISSION_STEPS));

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
  submission: { version: SUBMISSION_VERSION, fields: {}, capturedTests: {}, repair: null, updatedAt: null },
  submissionRevision: 0,
  submissionSyncTimer: null,
  submissionSyncInFlight: false,
  submissionSyncPending: false,
  submissionSyncConflict: false,
  submissionSaveMessage: 'Draft not yet saved',
  submissionPage: 'property',
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
    error.status = response.status;
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
  captureCompletedTest(snapshot.lastTest);
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
  $('jump-request-event').disabled = Boolean(app.snapshot && app.snapshot.activeTest);
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
  renderSubmission();
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
  $('jump-request-event').disabled = true;
  $('request-feedback').className = 'feedback';
  $('request-feedback').textContent = `Starting ${TESTS[testId].label}...`;
  try {
    const result = await api('/api/tests/run', { method: 'POST', body: JSON.stringify({ testId }) });
    app.events = [];
    app.latestSeq = 0;
    app.followLive = true;
    $('request-feedback').textContent = `${result.testRunId} started against ${result.buildId}.`;
  } catch (error) {
    $('jump-request-event').disabled = false;
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

function submissionStorageKey() {
  const studentId = app.session && app.session.student ? app.session.student.studentId : 'preview';
  return `cs6494-hw3-submission:${studentId}`;
}

function fieldLabel(id) {
  const label = document.querySelector(`label[for="${id}"]`);
  return label ? label.textContent.trim() : id;
}

function collectSubmissionFields() {
  for (const id of SUBMISSION_FIELD_IDS) {
    const field = $(id);
    if (field) app.submission.fields[id] = field.value.trim();
  }
}

function populateSubmissionFields() {
  for (const id of SUBMISSION_FIELD_IDS) {
    const field = $(id);
    const value = app.submission.fields[id];
    if (field && typeof value === 'string') field.value = value;
  }
}

function submissionTime(draft) {
  const value = draft && draft.updatedAt ? Date.parse(draft.updatedAt) : 0;
  return Number.isFinite(value) ? value : 0;
}

async function loadSubmissionDraft() {
  const empty = { version: SUBMISSION_VERSION, fields: {}, capturedTests: {}, repair: null, updatedAt: null };
  let local = null;
  try {
    const saved = JSON.parse(localStorage.getItem(submissionStorageKey()) || 'null');
    local = saved && saved.version === SUBMISSION_VERSION ? { ...empty, ...saved } : null;
  } catch (_error) {
    local = null;
  }
  let remote = null;
  try {
    const payload = await api('/api/submission');
    app.submissionRevision = Number(payload.revision) || 0;
    remote = payload.draft && payload.draft.version === SUBMISSION_VERSION
      ? { ...empty, ...payload.draft }
      : null;
  } catch (_error) {
    app.submissionSaveMessage = 'Server backup unavailable; saved in this browser';
  }
  app.submission = remote && submissionTime(remote) >= submissionTime(local) ? remote : (local || remote || empty);
  if (!app.submission.fields || typeof app.submission.fields !== 'object') app.submission.fields = {};
  if (!app.submission.capturedTests || typeof app.submission.capturedTests !== 'object') app.submission.capturedTests = {};
  if (!app.submission.fields['student-name'] && app.session && app.session.student) {
    app.submission.fields['student-name'] = app.session.student.label;
  }
  if (!app.submission.fields['test-prohibited-status']) app.submission.fields['test-prohibited-status'] = 'PROPOSED';
  if (!app.submission.fields['test-legitimate-status']) app.submission.fields['test-legitimate-status'] = 'PROPOSED';
  populateSubmissionFields();
  if (app.submission.updatedAt) {
    app.submissionSaveMessage = `Restored draft saved ${new Date(app.submission.updatedAt).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}`;
  }
  if (local && submissionTime(local) > submissionTime(remote)) queueSubmissionSync();
}

function saveSubmissionDraft() {
  collectSubmissionFields();
  app.submission.updatedAt = new Date().toISOString();
  try {
    localStorage.setItem(submissionStorageKey(), JSON.stringify(app.submission));
    app.submissionSaveMessage = `Saved in browser ${new Date(app.submission.updatedAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}; syncing`;
    queueSubmissionSync();
  } catch (_error) {
    app.submissionSaveMessage = 'Local save unavailable; trying private workspace';
    queueSubmissionSync();
  }
  renderSubmission();
}

function queueSubmissionSync(delay = 600) {
  if (!app.session || app.submissionSyncConflict) return;
  app.submissionSyncPending = true;
  if (app.submissionSyncTimer) window.clearTimeout(app.submissionSyncTimer);
  app.submissionSyncTimer = window.setTimeout(syncSubmissionDraft, delay);
}

async function syncSubmissionDraft() {
  if (!app.session || app.submissionSyncConflict) return false;
  if (app.submissionSyncInFlight) {
    app.submissionSyncPending = true;
    return false;
  }
  if (app.submissionSyncTimer) window.clearTimeout(app.submissionSyncTimer);
  app.submissionSyncTimer = null;
  app.submissionSyncInFlight = true;
  app.submissionSyncPending = false;
  const draft = JSON.parse(JSON.stringify(app.submission));
  try {
    const result = await api('/api/submission', {
      method: 'POST',
      body: JSON.stringify({ draft, baseRevision: app.submissionRevision })
    });
    app.submissionRevision = result.revision;
    app.submissionSaveMessage = `Saved to private workspace ${new Date(result.updatedAtUnixMs).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
    return true;
  } catch (error) {
    if (error.status === 409 && Number.isInteger(error.payload && error.payload.currentRevision)) {
      app.submissionSyncConflict = true;
      app.submissionSaveMessage = 'Another browser changed this draft. Stop editing and reload before continuing.';
    } else if (error.status === 409) {
      app.submissionSaveMessage = `Private workspace rejected this draft: ${error.message}`;
    } else {
      app.submissionSaveMessage = 'Saved in this browser; private workspace backup will retry';
      window.setTimeout(() => queueSubmissionSync(0), 3000);
    }
    return false;
  } finally {
    app.submissionSyncInFlight = false;
    if (app.submissionSyncPending && !app.submissionSyncConflict) queueSubmissionSync(0);
    renderSubmission();
  }
}

async function saveForLater() {
  saveSubmissionDraft();
  const saved = await syncSubmissionDraft();
  const feedback = $('submission-feedback');
  feedback.className = saved ? 'feedback good' : 'feedback error';
  feedback.textContent = saved
    ? 'Saved to your private workspace. You may close this browser and return with the same access code.'
    : app.submissionSaveMessage;
}

function captureCompletedTest(result) {
  if (!result || !result.testRunId || !app.session) return;
  const existing = app.submission.capturedTests[result.testId];
  if (existing && existing.testRunId === result.testRunId) return;
  const record = {
    testRunId: result.testRunId,
    testId: result.testId,
    status: result.status,
    passed: Boolean(result.passed),
    detail: result.detail,
    buildId: result.buildId,
    runId: result.runId,
    durationMs: result.durationMs,
    completedUnixMs: result.completedUnixMs || Date.now(),
    sourceSha256: app.snapshot && app.snapshot.build && app.snapshot.build.buildId === result.buildId
      ? app.snapshot.build.sourceSha256
      : null
  };
  app.submission.capturedTests[result.testId] = record;
  const prefix = result.testId === 'upstream_counterexample'
    ? 'test-prohibited'
    : result.testId === 'legitimate_restore'
      ? 'test-legitimate'
      : null;
  if (prefix) {
    app.submission.fields[`${prefix}-status`] = 'TESTED';
    app.submission.fields[`${prefix}-observed`] = `${result.status.toUpperCase()}: ${result.detail}`;
    app.submission.fields[`${prefix}-reference`] = `${result.testRunId}; run ${result.runId}; build ${result.buildId}`;
    populateSubmissionFields();
  }
  saveSubmissionDraft();
}

function captureActiveRepair() {
  const feedback = $('submission-feedback');
  if (!app.snapshot || app.dirtySource) {
    feedback.className = 'feedback error';
    feedback.textContent = 'Compile the current Structured Text successfully before capturing it as your repair.';
    setTab('controller');
    return;
  }
  app.submission.repair = {
    buildId: app.snapshot.build.buildId,
    sourceSha256: app.snapshot.build.sourceSha256,
    source: $('st-source').value,
    capturedAt: new Date().toISOString()
  };
  saveSubmissionDraft();
  feedback.className = 'feedback good';
  feedback.textContent = `Captured ${app.submission.repair.buildId}. Run both required regressions against this build.`;
}

function renderCapturedRuns() {
  const holder = $('captured-runs');
  holder.replaceChildren();
  const records = Object.values(app.submission.capturedTests).sort((a, b) => a.completedUnixMs - b.completedUnixMs);
  if (!records.length) {
    holder.textContent = 'No completed regression runs captured yet.';
    return;
  }
  for (const record of records) {
    const row = document.createElement('div');
    row.className = 'captured-run';
    const text = document.createElement('span');
    const label = TESTS[record.testId] ? TESTS[record.testId].label : record.testId;
    text.textContent = `${label} | ${record.testRunId} | ${record.buildId}`;
    const status = document.createElement('span');
    status.className = `tag ${record.passed ? 'allow' : 'deny'}`;
    status.textContent = record.status;
    row.append(text, status);
    holder.append(row);
  }
}

function stepIsComplete(step) {
  const fieldsComplete = SUBMISSION_STEPS[step].every(id => String(app.submission.fields[id] || '').trim());
  if (step === 'repair') return fieldsComplete && Boolean(app.submission.repair);
  if (step === 'tests' && fieldsComplete) {
    const bindings = [
      ['test-prohibited-status', 'upstream_counterexample'],
      ['test-legitimate-status', 'legitimate_restore']
    ];
    return bindings.every(([statusField, testId]) => {
      if (app.submission.fields[statusField] !== 'TESTED') return true;
      const record = app.submission.capturedTests[testId];
      return Boolean(record && app.submission.repair && record.buildId === app.submission.repair.buildId);
    });
  }
  return fieldsComplete;
}

function renderBuilderReview() {
  const list = $('builder-review-list');
  if (!list) return;
  list.replaceChildren();
  Object.keys(SUBMISSION_STEPS).forEach((step, index) => {
    const done = stepIsComplete(step);
    const item = document.createElement('li');
    item.className = done ? 'complete' : '';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'review-link';
    const number = document.createElement('span');
    number.className = 'review-number';
    number.textContent = String(index + 1);
    const title = document.createElement('strong');
    title.textContent = SUBMISSION_PAGE_TITLES[step];
    const state = document.createElement('span');
    state.className = 'review-state';
    state.textContent = done ? 'Complete' : 'Needs attention';
    button.append(number, title, state);
    button.addEventListener('click', () => setSubmissionPage(step));
    item.append(button);
    list.append(item);
  });
}

function renderSubmissionPage() {
  if (!$('submission-form')) return;
  const page = SUBMISSION_PAGE_ORDER.includes(app.submissionPage) ? app.submissionPage : 'property';
  const pageIndex = SUBMISSION_PAGE_ORDER.indexOf(page);
  const review = page === 'review';

  document.querySelectorAll('.builder-step').forEach(step => {
    const active = step.dataset.step === page;
    step.classList.toggle('active', active);
    step.open = active;
  });
  $('builder-identity').hidden = page !== 'property';
  $('builder-review-page').hidden = !review;
  document.querySelectorAll('[data-builder-page]').forEach(button => {
    const target = button.dataset.builderPage;
    const complete = target === 'review'
      ? Object.keys(SUBMISSION_STEPS).every(stepIsComplete)
      : stepIsComplete(target);
    button.classList.toggle('active', target === page);
    button.classList.toggle('complete', complete);
    if (target === page) button.setAttribute('aria-current', 'step');
    else button.removeAttribute('aria-current');
  });

  $('builder-back').disabled = pageIndex === 0;
  $('builder-next').hidden = review;
  $('builder-next').textContent = page === 'transfer' ? 'Review submission' : 'Continue';
  $('builder-page-title').textContent = SUBMISSION_PAGE_TITLES[page];
  $('builder-page-count').textContent = review ? 'Final review' : `Checkpoint ${pageIndex + 1} of 6`;
  $('builder-navigation-label').textContent = review ? 'Review and submit' : `Checkpoint ${pageIndex + 1} of 6`;
  renderBuilderReview();
}

function setSubmissionPage(page, { scroll = true } = {}) {
  if (!SUBMISSION_PAGE_ORDER.includes(page)) return;
  collectSubmissionFields();
  app.submissionPage = page;
  renderSubmissionPage();
  if (scroll) $('hw3-builder').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function openSubmissionBuilder(page = app.submissionPage) {
  $('hw3-builder').open = true;
  document.body.classList.add('submission-mode');
  setSubmissionPage(page, { scroll: false });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function closeSubmissionBuilder(tab = null) {
  collectSubmissionFields();
  saveSubmissionDraft();
  document.body.classList.remove('submission-mode');
  $('hw3-builder').open = false;
  if (tab) {
    setTab(tab);
    const target = tab === 'controller' ? $('panel-controller') : document.querySelector('.scenario-toolbar');
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function moveSubmissionPage(delta) {
  const current = SUBMISSION_PAGE_ORDER.indexOf(app.submissionPage);
  const next = Math.max(0, Math.min(SUBMISSION_PAGE_ORDER.length - 1, current + delta));
  setSubmissionPage(SUBMISSION_PAGE_ORDER[next]);
}

function renderSubmission() {
  if (!$('submission-form')) return;
  collectSubmissionFields();
  let complete = 0;
  document.querySelectorAll('.builder-step').forEach(step => {
    const done = stepIsComplete(step.dataset.step);
    if (done) complete += 1;
    step.classList.toggle('complete', done);
    step.querySelector('.step-state').textContent = done ? 'Complete' : 'Incomplete';
  });
  $('builder-progress').value = complete;
  $('builder-progress-label').textContent = `${complete} of 6 checkpoints complete`;
  $('autosave-status').textContent = app.submissionSaveMessage;
  if (app.submission.repair) {
    $('repair-capture-title').textContent = `Captured ${app.submission.repair.buildId}`;
    $('repair-capture-detail').textContent = `Source SHA-256 ${app.submission.repair.sourceSha256}`;
  } else {
    $('repair-capture-title').textContent = 'No controller build captured';
    $('repair-capture-detail').textContent = 'Compile your repair, then capture the active build.';
  }
  renderCapturedRuns();
  renderSubmissionPage();
}

function validateSubmission() {
  collectSubmissionFields();
  const issues = [];
  for (const id of SUBMISSION_FIELD_IDS) {
    if (!String(app.submission.fields[id] || '').trim()) issues.push({ field: id, message: `${fieldLabel(id)} is blank` });
  }
  if (!app.submission.repair) issues.push({ field: 'capture-repair', message: 'No compiled repair build is captured' });

  const requiredTests = [
    ['test-prohibited-status', 'upstream_counterexample', 'prohibited-transition'],
    ['test-legitimate-status', 'legitimate_restore', 'legitimate-service']
  ];
  for (const [statusField, testId, label] of requiredTests) {
    if (app.submission.fields[statusField] !== 'TESTED') continue;
    const record = app.submission.capturedTests[testId];
    if (!record) {
      issues.push({ field: statusField, message: `${label} evidence is labeled TESTED without a captured run` });
    } else if (app.submission.repair && record.buildId !== app.submission.repair.buildId) {
      issues.push({ field: statusField, message: `${label} ran against ${record.buildId}, not the captured repair ${app.submission.repair.buildId}` });
    }
  }
  return issues;
}

function appendReportSection(report, title, rows) {
  const section = document.createElement('section');
  const heading = document.createElement('h2');
  heading.textContent = title;
  const list = document.createElement('dl');
  for (const [label, value] of rows) {
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = value || 'Not provided';
    list.append(dt, dd);
  }
  section.append(heading, list);
  report.append(section);
}

function appendReportTests(report) {
  const section = document.createElement('section');
  const heading = document.createElement('h2');
  heading.textContent = '4. Regression evidence';
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const headerRow = document.createElement('tr');
  ['Test', 'Expected', 'Status', 'Observed or proposed', 'Evidence reference'].forEach(label => {
    const cell = document.createElement('th');
    cell.textContent = label;
    headerRow.append(cell);
  });
  head.append(headerRow);
  const body = document.createElement('tbody');
  const rows = [
    ['Prohibited transition', 'test-prohibited-expected', 'test-prohibited-status', 'test-prohibited-observed', 'test-prohibited-reference'],
    ['Legitimate restoration', 'test-legitimate-expected', 'test-legitimate-status', 'test-legitimate-observed', 'test-legitimate-reference']
  ];
  for (const [label, expected, status, observed, reference] of rows) {
    const row = document.createElement('tr');
    [label, app.submission.fields[expected], app.submission.fields[status], app.submission.fields[observed], app.submission.fields[reference]].forEach(value => {
      const cell = document.createElement('td');
      cell.textContent = value || 'Not provided';
      row.append(cell);
    });
    body.append(row);
  }
  table.append(head, body);
  section.append(heading, table);
  report.append(section);
}

function buildSubmissionReport() {
  collectSubmissionFields();
  const fields = app.submission.fields;
  const report = $('submission-report');
  report.replaceChildren();
  report.setAttribute('aria-hidden', 'false');

  const heading = document.createElement('header');
  const title = document.createElement('h1');
  title.textContent = 'HW3: From Requirement to Defensible Guardrail';
  const meta = document.createElement('p');
  meta.textContent = `${fields['student-name']} | ${fields['student-unid']} | Generated ${new Date().toLocaleString()}`;
  heading.append(title, meta);
  report.append(heading);

  appendReportSection(report, '1. Property and boundary', [
    ['Prohibited outcome', fields['property-prohibited']],
    ['Useful operation', fields['property-service']],
    ['Requirement source', fields['property-source']],
    ['Enforcement boundary', fields['property-boundary']]
  ]);
  appendReportSection(report, '2. Counterexample', [
    ['Initial state', fields['counter-initial']],
    ['Request', fields['counter-request']],
    ['Controller decision', fields['counter-decision']],
    ['First prohibited effect', fields['counter-effect']],
    ['Omitted dependency', fields['counter-omission']]
  ]);
  appendReportSection(report, '3. Repair', [
    ['Rationale', fields['repair-explanation']],
    ['Captured build', app.submission.repair ? app.submission.repair.buildId : 'Not captured'],
    ['Source SHA-256', app.submission.repair ? app.submission.repair.sourceSha256 : 'Not captured']
  ]);
  appendReportTests(report);
  appendReportSection(report, '5. Assumption stress test', [
    ['Expired assumption', fields['stress-assumption']],
    ['Evidence no longer sufficient', fields['stress-evidence']],
    ['Recheck location', fields['stress-recheck']],
    ['Positive-service regression', fields['stress-positive']]
  ]);
  appendReportSection(report, '6. Transfer and bounded claim', [
    ['Utility fragment', fields['transfer-context']],
    ['Property', fields['transfer-property']],
    ['Missing evidence', fields['transfer-missing']],
    ['Likely enforcement point', fields['transfer-enforcement']],
    ['First assumption to test', fields['transfer-assumption']],
    ['Under assumptions', fields['claim-assumptions']],
    ['Evidence', fields['claim-evidence']],
    ['Supports the claim that', fields['claim-supports']],
    ['Does not establish', fields['claim-limits']]
  ]);

  const appendix = document.createElement('section');
  appendix.className = 'report-appendix';
  const appendixHeading = document.createElement('h2');
  appendixHeading.textContent = 'Evidence appendix';
  const buildMeta = document.createElement('p');
  buildMeta.textContent = app.submission.repair
    ? `Captured build ${app.submission.repair.buildId}; source SHA-256 ${app.submission.repair.sourceSha256}.`
    : 'No compiled build captured.';
  const code = document.createElement('pre');
  code.textContent = app.submission.repair ? app.submission.repair.source : 'No Structured Text captured.';
  appendix.append(appendixHeading, buildMeta, code);
  const records = Object.values(app.submission.capturedTests);
  if (records.length) {
    const runHeading = document.createElement('h3');
    runHeading.textContent = 'Captured run manifest';
    const runList = document.createElement('ul');
    for (const record of records) {
      const item = document.createElement('li');
      item.textContent = `${record.testId}: ${record.status}; ${record.testRunId}; run ${record.runId}; build ${record.buildId}`;
      runList.append(item);
    }
    appendix.append(runHeading, runList);
  }
  report.append(appendix);
}

function reviewSubmission(printAfterReview = false) {
  saveSubmissionDraft();
  const issues = validateSubmission();
  const feedback = $('submission-feedback');
  if (issues.length) {
    feedback.className = 'feedback error';
    feedback.textContent = `${issues.length} item${issues.length === 1 ? '' : 's'} need attention: ${issues.slice(0, 3).map(issue => issue.message).join('; ')}${issues.length > 3 ? '; ...' : ''}`;
    const target = $(issues[0].field);
    if (target) {
      const step = target.closest('.builder-step');
      openSubmissionBuilder(step ? step.dataset.step : 'property');
      window.setTimeout(() => target.focus(), 250);
    }
    return;
  }
  buildSubmissionReport();
  const failedTests = Object.values(app.submission.capturedTests).filter(record => record.status === 'failed');
  feedback.className = failedTests.length ? 'feedback' : 'feedback good';
  feedback.textContent = failedTests.length
    ? `Submission is structurally complete, but ${failedTests.length} captured regression${failedTests.length === 1 ? '' : 's'} failed. The PDF will preserve that result for grading.`
    : 'Submission is complete and internally consistent. Use the browser dialog to save one PDF for Canvas.';
  if (!printAfterReview) return;
  const originalTitle = document.title;
  const safeUnid = app.submission.fields['student-unid'].replace(/[^A-Za-z0-9_-]/g, '');
  document.title = `HW3_${safeUnid}`;
  window.addEventListener('afterprint', () => {
    document.title = originalTitle;
    $('submission-report').setAttribute('aria-hidden', 'true');
  }, { once: true });
  window.print();
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
  await loadSubmissionDraft();
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
  $('capture-repair').addEventListener('click', captureActiveRepair);
  $('review-submission').addEventListener('click', () => reviewSubmission(false));
  $('print-submission').addEventListener('click', () => reviewSubmission(true));
  $('save-submission-later').addEventListener('click', saveForLater);
  $('open-submission').addEventListener('click', () => openSubmissionBuilder());
  $('close-builder').addEventListener('click', () => closeSubmissionBuilder());
  $('open-controller-workspace').addEventListener('click', () => closeSubmissionBuilder('controller'));
  $('open-test-runner').addEventListener('click', () => closeSubmissionBuilder('requests'));
  $('builder-back').addEventListener('click', () => moveSubmissionPage(-1));
  $('builder-next').addEventListener('click', () => moveSubmissionPage(1));
  document.querySelectorAll('[data-builder-page]').forEach(button => {
    button.addEventListener('click', () => setSubmissionPage(button.dataset.builderPage));
  });
  document.querySelectorAll('.builder-step > summary').forEach(summary => {
    summary.addEventListener('click', event => event.preventDefault());
  });
  $('hw3-builder').addEventListener('toggle', () => {
    document.body.classList.toggle('submission-mode', $('hw3-builder').open);
    if ($('hw3-builder').open) renderSubmissionPage();
  });
  $('submission-form').querySelectorAll('input, textarea, select').forEach(field => {
    field.addEventListener('input', saveSubmissionDraft);
    field.addEventListener('change', saveSubmissionDraft);
  });
  $('sign-out').addEventListener('click', logout);
  window.addEventListener('pagehide', () => {
    if (!app.session || !app.submissionSyncPending || app.submissionSyncConflict) return;
    fetch(`${LAB_BASE}/api/submission`, {
      method: 'POST',
      cache: 'no-store',
      keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft: app.submission, baseRevision: app.submissionRevision })
    }).catch(() => {});
  });
  renderSubmission();
  poll();
}

function showLogin(message = '') {
  app.polling = false;
  app.session = null;
  document.body.classList.remove('submission-mode');
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
