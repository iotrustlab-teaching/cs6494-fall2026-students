const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../data/scenario.js"), "utf8"), context);

const assets = context.window.WORKBENCH_SCENARIO.assets;
assert.equal(assets.length, 9);
assert.equal(new Set(assets.map((asset) => asset.ip)).size, assets.length);
assert.equal(assets.filter((asset) => asset.source === "packet + site record").length, 3);
assert.equal(assets.filter((asset) => asset.source === "site record only").length, 6);
assert.ok(assets.every((asset) => asset.ip.startsWith("192.0.2.")));
assert.ok(context.window.WORKBENCH_SCENARIO.cases.some((item) => item.id === "stale"));
const baseline = context.window.WORKBENCH_SCENARIO.cases.find((item) => item.id === "baseline");
assert.match(baseline.label, /authored/i);
for (const packet of ["Packet #4", "Packet #5", "Packet #6", "Packet #8", "Packet #10"]) {
  assert.ok(baseline.steps.some((step) => step[1] === packet), `${packet} must be cited in the baseline replay`);
}
console.log("Scenario verified: 3 packet endpoints, 6 unverified site leads, fictional addresses.");
