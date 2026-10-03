(function (root) {
  "use strict";
  const GROUPS = ["Engineering", "Supervisory", "Control", "Process I/O", "Infrastructure", "Remote / vendor", "Unassigned"];

  function operation(event) {
    if (event.operation === "read" || event.operation === "write") return event.operation;
    return event.function === 6 || event.function === 16 ? "write" : "read";
  }

  function evaluate(event, groups, rules) {
    const source = groups[event.source] || "Unassigned";
    const destination = groups[event.destination] || "Unassigned";
    const op = operation(event);
    const match = rules.find((rule) =>
      (rule.source === "Any" || rule.source === source) &&
      (rule.destination === "Any" || rule.destination === destination) &&
      (rule.operation === "any" || rule.operation === op)
    );
    return { action: match ? match.action : "allow", rule: match ? match.id : "default allow", source, destination, operation: op };
  }

  root.WORKBENCH_POLICY = { GROUPS, operation, evaluate };
})(globalThis);
