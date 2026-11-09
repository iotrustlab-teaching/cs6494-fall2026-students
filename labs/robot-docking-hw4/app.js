(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const NS = 'http://www.w3.org/2000/svg';
  const FIELDS = ['time', 'position', 'velocity', 'distance', 'observed_remaining', 'commanded_speed'];
  const MS_PER_MODEL_SECOND = 850;
  const reducedMotion = typeof window === 'undefined' ? {matches: false} :
    window.matchMedia('(prefers-reduced-motion: reduce)');
  let current = null, playback = null, trusted = false, revealed = false;
  let stateIndex = 0, frameRequest = null, playing = false, animationOrigin = 0;

  function svg(tag, attributes = {}, label) {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
    if (label !== undefined) node.textContent = String(label);
    return node;
  }

  async function api(path, value) {
    const options = value === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: typeof value === 'string' ? value : JSON.stringify(value),
    };
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  function status(message, isError = false) {
    $('status').textContent = message;
    $('status').classList.toggle('error', isError);
  }

  function isState(point) {
    return point && FIELDS.every(field => typeof point[field] === 'number' && Number.isFinite(point[field])) &&
      point.distance >= 0 && point.observed_remaining >= 0 && point.commanded_speed >= 0 &&
      Math.abs(point.distance - Math.abs(point.position)) <= 0.001;
  }

  function preparePlayback(record) {
    if (!record || typeof record !== 'object' || !Array.isArray(record.samples) ||
        record.samples.length !== 8 || record.samples.some((point, index) =>
          !isState(point) || Math.abs(point.time - index) > 1e-8)) {
      throw Error('eight complete one-second states at t = 0–7 are required');
    }
    if (record.trace != null && !Array.isArray(record.trace)) throw Error('recorded trace must be an array');
    const dense = Array.isArray(record.trace) && record.trace.length > 0;
    const states = dense ? record.trace : record.samples;
    if (states.some(point => !isState(point)) || Math.abs(states[0].time) > 1e-8 ||
        Math.abs(states.at(-1).time - 7) > 1e-8 ||
        states.some((point, index) => index > 0 && point.time <= states[index - 1].time)) {
      throw Error('recorded states must be complete and ordered from 0 to 7 seconds');
    }
    if (dense) {
      for (const sample of record.samples) {
        const matching = states.find(point => Math.abs(point.time - sample.time) < 1e-8);
        if (!matching || FIELDS.some(field => Math.abs(matching[field] - sample[field]) > 1e-7)) {
          throw Error('monitor samples do not match the recorded dense states');
        }
      }
    }
    const positions = states.map(point => point.position);
    const worldMin = Math.min(-3.3, ...positions.map(value => value - 0.35));
    const worldMax = Math.max(1.1, ...positions.map(value => value + 0.35));
    return {states, samples: record.samples, dense, worldMin, worldMax,
      xWorld: position => 54 + (position - worldMin) * 892 / (worldMax - worldMin),
      distanceMax: Math.max(0.7, ...record.samples.map(point => point.distance * 1.13)),
      speedMax: Math.max(0.4, ...record.samples.map(point => Math.abs(point.velocity) * 1.16))};
  }

  async function refreshPolicy() {
    try {
      const data = await api('/api/status');
      $('brake-at').textContent = `${data.policy.brake_at_m.toFixed(2)} m`;
      $('formulae').textContent = `Service: ${data.formulae.service}\nSafety: ${data.formulae.safety}`;
      if (trusted && current && current.policy.brake_at_m !== data.policy.brake_at_m) {
        $('reveal').disabled = true;
        $('results').hidden = true;
        $('trace-highlights').hidden = true;
        revealed = false;
        renderFrame(stateIndex);
        $('run-id').textContent = `Run ${current.run_id} · previous policy`;
        status('Policy changed. The visible trace used the previous policy; click Run for a new execution.');
      } else status('Python model and RTAMT ready. Changing policy.json affects the next fresh run.');
    } catch (error) { status(`Engine unavailable: ${error.message}`, true); }
  }

  function setSceneLayout() {
    const x = playback.xWorld, dock = x(0), left = x(-0.5), right = x(0.5);
    $('service-zone').setAttribute('x', left);
    $('service-zone').setAttribute('width', right - left);
    for (const id of ['zone-left', 'zone-right']) {
      const at = id === 'zone-left' ? left : right;
      $(id).setAttribute('x1', at); $(id).setAttribute('x2', at);
    }
    $('dock-line').setAttribute('x1', dock);
    $('dock-line').setAttribute('x2', dock);
    $('dock-marker').setAttribute('transform', `translate(${dock},0)`);
    $('dock-label').setAttribute('x', dock);
    $('zone-label').setAttribute('x', left - 10);
    const ticks = $('scene-ticks');
    ticks.replaceChildren();
    for (let value = Math.ceil(playback.worldMin); value <= Math.floor(playback.worldMax); value++) {
      const at = x(value);
      ticks.append(svg('line', {x1: at, y1: 246, x2: at, y2: 252, stroke: '#92a5b1'}));
      ticks.append(svg('text', {x: at, y: 270}, `${value} m`));
    }
    $('scene-empty').hidden = true;
    $('robot-figure').setAttribute('visibility', 'visible');
  }

  function moment(state) {
    const moving = Math.abs(state.velocity) > 0.005;
    if (Math.abs(state.commanded_speed) < 1e-9 && moving) return [
      'Stop requested; still moving.', state.position > 0 ?
        'The robot has passed x = 0, but braking is still in progress.' :
        'The controller requested zero speed; braking takes time.'];
    if (state.position > 0.5) return ['Past the target and outside the region.', 'Signed position shows which side of the dock the robot is on.'];
    if (state.position > 0 && state.distance <= 0.5) return ['Past the target; still within 0.5 m.', 'Absolute distance alone does not show the side of the dock.'];
    if (!moving && state.distance <= 0.5) return ['Stopped within 0.5 m of the dock.', 'The checker still needs the relevant one-second samples.'];
    if (state.distance <= 0.5) return ['Inside the 0.5 m region.', 'The displayed speed matters when the monitor samples this moment.'];
    if (!moving && state.commanded_speed > 0) return ['Motion requested; robot still at rest.', 'Commanded and actual speed are different signals.'];
    return ['Approaching the docking region.', 'Follow the measured speed as the robot closes in.'];
  }

  function stopMotion() {
    if (frameRequest !== null) cancelAnimationFrame(frameRequest);
    frameRequest = null; playing = false;
    $('animate').textContent = 'Play animation';
    $('animate').setAttribute('aria-pressed', 'false');
  }

  function nearestStateIndex(time) {
    let low = 0, high = playback.states.length - 1;
    while (low < high) {
      const middle = Math.ceil((low + high) / 2);
      if (playback.states[middle].time <= time) low = middle;
      else high = middle - 1;
    }
    return low;
  }

  function renderChart(id, key, limit, maximum, color) {
    const target = $(id);
    target.replaceChildren();
    const x = time => 58 + 93 * time;
    const y = value => 205 - 160 * value / maximum;
    const time = playback.states[stateIndex].time;
    if (key === 'distance') target.append(svg('rect', {x: 52, y: y(limit), width: 668,
      height: y(0) - y(limit), fill: '#e8f1f5'}));
    target.append(svg('line', {x1: 52, y1: y(limit), x2: 720, y2: y(limit),
      stroke: '#537f96', 'stroke-width': 2, 'stroke-dasharray': '7 5'}));
    target.append(svg('text', {x: 55, y: 23, fill: '#506474', 'font-size': 15},
      key === 'distance' ? 'region ≤ 0.50 m' : 'speed limit 0.20 m/s when inside, seconds 0–5'));
    target.append(svg('polyline', {points: playback.samples.map(point =>
      `${x(point.time)},${y(key === 'distance' ? point.distance : Math.abs(point.velocity))}`).join(' '),
      fill: 'none', stroke: color, 'stroke-width': 3}));
    target.append(svg('line', {x1: x(time), y1: 31, x2: x(time), y2: 215,
      stroke: '#334c5d', 'stroke-width': 2, 'stroke-dasharray': '4 4'}));
    const service = trusted && revealed ? current.monitor.service : null;
    const safety = trusted && revealed ? current.monitor.safety : null;
    const serviceStart = service && service.pass ? service.first_window_start_s : null;
    playback.samples.forEach((point, index) => {
      const value = key === 'distance' ? point.distance : Math.abs(point.velocity);
      const cx = x(point.time), cy = y(value);
      const group = svg('g', {'class': 'chart-sample', role: 'button', tabindex: 0,
        'aria-label': `Go to monitored sample at second ${point.time}`});
      group.append(svg('circle', {cx, cy, r: 17, fill: 'transparent'}));
      if (key === 'distance' && serviceStart !== null && index >= serviceStart && index < serviceStart + 3) {
        group.append(svg('circle', {cx, cy, r: 12, fill: 'none', stroke: '#11744c', 'stroke-width': 3}));
      }
      const violation = key === 'velocity' && safety && safety.too_fast_samples_s.includes(index);
      const beyondSpeedHorizon = key === 'velocity' && index > 5;
      group.append(svg('circle', {cx, cy, r: index === Math.round(time) ? 7 : 5,
        fill: violation ? '#aa1029' : beyondSpeedHorizon ? '#8da2b0' : color,
        stroke: '#fff', 'stroke-width': 2}));
      group.append(svg('text', {x: cx, y: Math.max(41, cy - 13), 'text-anchor': 'middle',
        fill: '#27394a', 'font-size': 13}, value.toFixed(2)));
      group.append(svg('text', {x: cx, y: 241, 'text-anchor': 'middle', fill: '#506474', 'font-size': 14}, String(index)));
      const jump = () => {
        stopMotion(); setTime(point.time);
        const match = $(id).querySelectorAll('.chart-sample')[index];
        if (match) match.focus();
      };
      group.addEventListener('click', jump);
      group.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); jump(); }
      });
      target.append(group);
    });
  }

  function drawSampleRows() {
    const rows = playback.samples.map(point => {
      const row = document.createElement('tr');
      row.dataset.time = String(point.time);
      const timeCell = document.createElement('td');
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'sample-jump';
      button.textContent = point.time.toFixed(0);
      button.setAttribute('aria-label', `Move playhead to second ${point.time}`);
      button.addEventListener('click', () => { stopMotion(); setTime(point.time); });
      timeCell.append(button); row.append(timeCell);
      for (const value of [point.distance, point.observed_remaining,
        Math.abs(point.velocity), point.commanded_speed]) {
        row.append(Object.assign(document.createElement('td'), {textContent: value.toFixed(3)}));
      }
      const cue = document.createElement('td'); cue.className = 'sample-cue'; row.append(cue);
      return row;
    });
    $('sample-rows').replaceChildren(...rows);
  }

  function updateSampleRows() {
    const currentTime = playback.states[stateIndex].time;
    const nearest = Math.max(0, Math.min(7, Math.round(currentTime)));
    const service = trusted && revealed ? current.monitor.service : null;
    const safety = trusted && revealed ? current.monitor.safety : null;
    const serviceStart = service && service.pass ? service.first_window_start_s : null;
    $('sample-rows').querySelectorAll('tr').forEach((row, index) => {
      const witness = serviceStart !== null && index >= serviceStart && index < serviceStart + 3;
      const violation = Boolean(safety && safety.too_fast_samples_s.includes(index));
      row.classList.toggle('selected-sample', index === nearest);
      row.classList.toggle('service-witness', witness);
      row.classList.toggle('speed-violation', violation);
      row.querySelector('.sample-cue').textContent = revealed && trusted ?
        [witness ? 'Stay window' : '', violation ? 'Too fast' : ''].filter(Boolean).join(' · ') : '';
    });
    $('sample-focus').textContent = playback.dense ?
      `Current recorded state: t = ${currentTime.toFixed(2)} s. Highlighted row: nearest monitored sample at ${nearest} s; the checker uses only whole-second samples.` :
      `Sample-only view: highlighted monitored sample at ${nearest} s. No motion between these samples was supplied.`;
  }

  function renderFrame(index) {
    if (!playback) return;
    stateIndex = Math.max(0, Math.min(playback.states.length - 1, index));
    const point = playback.states[stateIndex];
    $('robot-figure').setAttribute('transform', `translate(${playback.xWorld(point.position)},0)`);
    $('scene-time').textContent = `t = ${point.time.toFixed(2)} s`;
    $('scene-position').textContent = `signed x = ${point.position >= 0 ? '+' : ''}${point.position.toFixed(2)} m`;
    $('robot-command-text').textContent = Math.abs(point.commanded_speed) < 1e-9 ?
      'STOP · 0.00 m/s' : `MOVE · ${point.commanded_speed.toFixed(2)} m/s`;
    const [main, detail] = moment(point);
    $('moment-summary').textContent = main; $('moment-detail').textContent = detail;
    $('command-value').textContent = `${point.commanded_speed.toFixed(2)} m/s`;
    $('speed-value').textContent = `${Math.abs(point.velocity).toFixed(2)} m/s`;
    $('distance-value').textContent = `${point.distance.toFixed(3)} m`;
    $('observed-value').textContent = `${point.observed_remaining.toFixed(3)} m`;
    $('reference-value').textContent = `${point.distance.toFixed(3)} m`;
    $('signed-value').textContent = `${point.position >= 0 ? '+' : ''}${point.position.toFixed(3)} m`;
    $('playback-time').textContent = `t = ${point.time.toFixed(2)} s`;
    $('playhead').value = String(stateIndex);
    $('playhead').setAttribute('aria-valuetext', `${point.time.toFixed(2)} seconds`);
    renderChart('distance-chart', 'distance', 0.5, playback.distanceMax, '#a33c4d');
    renderChart('speed-chart', 'velocity', 0.2, playback.speedMax, '#185d92');
    updateSampleRows();
  }

  function setTime(time) {
    if (!playback) return;
    const index = playback.states.findIndex(point => Math.abs(point.time - time) < 1e-8);
    renderFrame(index >= 0 ? index : nearestStateIndex(time));
  }

  function setUnavailable(message) {
    stopMotion(); current = null; playback = null; trusted = false; revealed = false;
    $('run-id').textContent = 'No usable run';
    $('scene-empty').hidden = false;
    $('scene-empty').textContent = `Playback unavailable: ${message}`;
    $('robot-figure').setAttribute('visibility', 'hidden');
    $('scene-time').textContent = '';
    $('scene-position').textContent = '';
    $('moment-summary').textContent = 'No usable motion record.';
    $('moment-detail').textContent = message;
    for (const id of ['command-value', 'speed-value', 'distance-value',
      'observed-value', 'reference-value', 'signed-value']) $(id).textContent = '—';
    for (const id of ['distance-chart', 'speed-chart']) $(id).replaceChildren();
    $('sample-rows').innerHTML = '<tr><td colspan="6">No complete recorded states available.</td></tr>';
    $('results').hidden = true; $('trace-highlights').hidden = true;
    for (const id of ['animate', 'previous-sample', 'next-sample', 'restart-view', 'playhead', 'reveal', 'download']) $(id).disabled = true;
    $('playback-time').textContent = 't = —'; $('sample-focus').textContent = message;
    $('playback-note').textContent = 'A complete signed-position record is needed to show the robot without guessing its motion.';
    status(`Playback unavailable: ${message}`, true);
  }

  function showRun(record, message, isTrusted = true) {
    stopMotion();
    let prepared;
    try { prepared = preparePlayback(record); }
    catch (error) { setUnavailable(error.message); return false; }
    current = record; playback = prepared; trusted = isTrusted; revealed = false;
    $('run-id').textContent = isTrusted ? `Run ${record.run_id}` :
      `View only${record.run_id ? ` · ${record.run_id}` : ''}`;
    if (isTrusted && record.policy && typeof record.policy.brake_at_m === 'number') {
      $('brake-at').textContent = `${record.policy.brake_at_m.toFixed(2)} m`;
    }
    $('results').hidden = true; $('trace-highlights').hidden = true;
    $('reveal').disabled = !isTrusted || !record.monitor;
    $('download').disabled = !isTrusted;
    $('animate').disabled = reducedMotion.matches;
    for (const id of ['previous-sample', 'next-sample', 'restart-view', 'playhead']) $(id).disabled = false;
    $('playhead').max = String(prepared.states.length - 1); $('playhead').step = '1';
    $('playback-note').textContent = prepared.dense ?
      'Play animation follows recorded 0.05-second states. It does not run the model again; only the dots at whole seconds are monitored.' :
      'Sample-only playback: positions jump between supplied one-second states. No intermediate trajectory or new model run is implied.';
    if (reducedMotion.matches) $('playback-note').textContent += ' Reduced-motion preference is on; use the sample buttons or scrubber.';
    setSceneLayout(); drawSampleRows(); renderFrame(0); status(message);
    return true;
  }

  function play() {
    if (!playback || reducedMotion.matches) return;
    if (playing) { stopMotion(); return; }
    if (stateIndex === playback.states.length - 1) renderFrame(0);
    playing = true;
    animationOrigin = performance.now() - playback.states[stateIndex].time * MS_PER_MODEL_SECOND;
    $('animate').textContent = 'Pause animation'; $('animate').setAttribute('aria-pressed', 'true');
    function frame(now) {
      if (!playing) return;
      const targetTime = Math.min(7, (now - animationOrigin) / MS_PER_MODEL_SECOND);
      const index = nearestStateIndex(targetTime);
      if (index !== stateIndex) renderFrame(index);
      if (targetTime >= 7) { renderFrame(playback.states.length - 1); stopMotion(); }
      else frameRequest = requestAnimationFrame(frame);
    }
    frameRequest = requestAnimationFrame(frame);
  }

  function stepSample(direction) {
    if (!playback) return;
    stopMotion();
    const time = playback.states[stateIndex].time;
    const next = direction > 0 ? Math.floor(time + 1e-8) + 1 : Math.ceil(time - 1e-8) - 1;
    setTime(Math.max(0, Math.min(7, next)));
  }

  function reveal() {
    if (!current || !trusted || !current.monitor) return;
    const service = current.monitor.service, safety = current.monitor.safety;
    const results = $('results'); results.replaceChildren();
    const lines = [
      ['Useful service', service.pass ? 'PASS' : 'FAIL', `distance margin ${service.margin_m >= 0 ? '+' : ''}${service.margin_m.toFixed(3)} m; first stay window starts ${service.first_window_start_s === null ? 'never' : `${service.first_window_start_s} s`}`],
      ['Slow whenever inside', safety.pass ? 'PASS' : 'FAIL',
        `antecedent ${safety.exercised ? 'EXERCISED' : 'NOT EXERCISED'}; normalized RTAMT score ${safety.robustness_normalized >= 0 ? '+' : ''}${safety.robustness_normalized.toFixed(3)}; too-fast samples ${safety.too_fast_samples_s.length ? safety.too_fast_samples_s.join(', ') + ' s' : 'none'}`],
    ];
    for (const [label, verdict, detail] of lines) {
      const row = document.createElement('div'), bold = document.createElement('strong'), badge = document.createElement('span');
      bold.textContent = `${label}: `; badge.className = verdict === 'PASS' ? 'pass' : 'fail'; badge.textContent = verdict;
      row.append(bold, badge, document.createTextNode(` · ${detail}`)); results.append(row);
    }
    revealed = true; results.hidden = false;
    const witness = service.pass ?
      `Stay window: ${service.first_window_start_s}, ${service.first_window_start_s + 1}, ${service.first_window_start_s + 2} s.` :
      'No successful three-sample stay window.';
    const failures = safety.too_fast_samples_s.length ?
      `Too fast inside at ${safety.too_fast_samples_s.join(', ')} s.` :
      `No too-fast monitored sample${safety.exercised ? '' : '; the inside condition was not exercised'}.`;
    $('trace-highlights').textContent = `${witness} ${failures} Speed was checked only through second 5.`;
    $('trace-highlights').hidden = false; renderFrame(stateIndex);
  }

  async function run() {
    $('run').disabled = true;
    status('Resetting and executing the Python model, then checking RTAMT…');
    try {
      const data = await api('/api/run', {cruise_speed_m_s: Number($('speed').value), braking_m_s2: Number($('braking').value)});
      showRun(data, 'Fresh model run complete. Watch the motion, inspect the trace, then reveal the fixed checks.');
    } catch (error) { status(`Run failed: ${error.message}`, true); }
    finally { $('run').disabled = false; }
  }

  function download() {
    if (!current || !trusted) return;
    const link = document.createElement('a');
    // Use Python's saved bytes; re-stringifying floats may invalidate a trace hash.
    link.href = `/api/download/${current.run_id}`;
    link.download = `hw4_run_${current.run_id}.json`;
    link.click();
  }

  async function replayFile() {
    const file = $('saved-file').files[0];
    if (!file) { $('replay-status').textContent = 'Choose a saved JSON file first.'; return; }
    $('replay-file').disabled = true;
    $('replay-status').textContent = 'Re-executing the saved scenario and policy…';
    try {
      // Preserve numeric spelling: parse/stringify can turn Python's 0.0 into 0.
      const proof = await api('/api/replay', await file.text());
      $('replay-status').textContent = `Verified replay of ${proof.original_run_id}: maximum state difference ${proof.max_state_error} (tolerance ${proof.tolerance}).`;
      showRun(proof.replayed_run, 'Verified replay execution. This trace was regenerated, not loaded from a saved curve.');
    } catch (error) { $('replay-status').textContent = `Replay failed: ${error.message}`; }
    finally { $('replay-file').disabled = false; }
  }

  async function viewFile() {
    const file = $('view-file').files[0];
    if (!file) { $('view-status').textContent = 'Choose a JSON file to view.'; return; }
    if (file.size > 3_000_000) {
      setUnavailable('view-only file is too large (3 MB limit)');
      $('view-status').textContent = 'View-only file is too large (3 MB limit).';
      return;
    }
    try {
      const record = JSON.parse(await file.text());
      const shown = showRun(record, 'Viewing saved values only. No Python execution, replay proof, or new RTAMT check occurred.', false);
      $('view-status').textContent = shown ?
        `View only: ${playback.dense ? 'recorded dense states' : 'one-second samples'}; no new run or verdict.` :
        'This file does not contain complete states for the robot view.';
    } catch (error) { setUnavailable(error.message); $('view-status').textContent = `Cannot view file: ${error.message}`; }
  }

  function preset(speed, braking) {
    $('speed').value = speed; $('braking').value = braking;
    $('reveal').disabled = true; $('results').hidden = true; $('trace-highlights').hidden = true;
    revealed = false; if (playback) renderFrame(stateIndex);
    status('Scenario selected. Click Run for a fresh trace.');
  }

  // Keep the data contract testable without a browser or a second simulator.
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {preparePlayback, moment};
    return;
  }

  $('preset-baseline').addEventListener('click', () => preset(1.2, 0.5));
  $('preset-a').addEventListener('click', () => preset(1.2, 0.6));
  $('preset-b').addEventListener('click', () => preset(1.2, 1.6));
  for (const id of ['speed', 'braking']) $(id).addEventListener('input', () => {
    $('reveal').disabled = true; $('results').hidden = true; $('trace-highlights').hidden = true;
    revealed = false; if (playback) renderFrame(stateIndex);
    status('Inputs changed. Click Run for a fresh trace.');
  });
  $('refresh-policy').addEventListener('click', refreshPolicy);
  $('run').addEventListener('click', run);
  $('animate').addEventListener('click', play);
  $('previous-sample').addEventListener('click', () => stepSample(-1));
  $('next-sample').addEventListener('click', () => stepSample(1));
  $('restart-view').addEventListener('click', () => { stopMotion(); renderFrame(0); });
  $('playhead').addEventListener('input', () => { stopMotion(); renderFrame(Number($('playhead').value)); });
  $('reveal').addEventListener('click', reveal);
  $('download').addEventListener('click', download);
  $('replay-file').addEventListener('click', replayFile);
  $('view-file-button').addEventListener('click', viewFile);
  if (reducedMotion.addEventListener) reducedMotion.addEventListener('change', () => {
    if (reducedMotion.matches) stopMotion();
    $('animate').disabled = !playback || reducedMotion.matches;
    if (playback) $('playback-note').textContent =
      `${playback.dense ? 'Animation follows recorded 0.05-second states.' : 'Sample-only playback has no intermediate states.'} ` +
      (reducedMotion.matches ? 'Reduced-motion preference is on; use the sample buttons or scrubber.' :
        'Playback does not execute the model.');
  });
  refreshPolicy();
})();
