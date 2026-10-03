const assert = require("node:assert/strict");
require("../static/policy.js");

const { evaluate } = globalThis.WORKBENCH_POLICY;
const groups = { "192.0.2.11": "Supervisory", "192.0.2.20": "Control" };
const denyWrites = [{ id: "r1", source: "Supervisory", destination: "Control", operation: "write", action: "deny" }];
const unsafe = { source: "192.0.2.11", destination: "192.0.2.20", function: 6 };
const legitimate = { ...unsafe, origin: "authored service test" };
const read = { ...unsafe, function: 3 };

assert.equal(evaluate(unsafe, groups, denyWrites).action, "deny");
assert.equal(evaluate(legitimate, groups, denyWrites).action, "deny");
assert.equal(evaluate(read, groups, denyWrites).action, "allow");
assert.equal(evaluate(unsafe, groups, []).action, "allow");
assert.equal(evaluate(unsafe, groups, [{ id: "r0", source: "Engineering", destination: "Control", operation: "write", action: "deny" }]).action, "allow");
assert.equal(evaluate(unsafe, groups, [{ id: "r2", source: "Any", destination: "Control", operation: "any", action: "deny" }]).action, "deny");
console.log("Policy simulation verified: unsafe and legitimate writes share the same network match.");
