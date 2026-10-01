# Substation Recovery Lab sequence

Use the same station for all five beats. Students should predict an outcome
before each run, inspect the evidence afterward, and distinguish controller
permission from actual breaker position and electrical consequence.

## 1. Zero-current ambiguity

**Question:** Are two disconnected configurations equivalent because both report
zero volts and zero current?

1. Open **Controller ST** and load **Vulnerable: present current only**.
2. Compile and activate it.
3. In **Requests**, select **Upstream-close counterexample**.
4. Before running, note that B0 is open, S3 is positioned closed, and current is zero.
5. Predict whether `CLOSE B0` will be permitted.

The key distinction is topology. Present current describes the disconnected
state, not what the requested transition will energize.

## 2. Unsafe upstream close

Run **Upstream-close counterexample** against the vulnerable build. Follow the
timeline from request to controller decision, actual B0 position, S3 current,
and protection trip.

**Evidence question:** Which event proves that the request was accepted, and
which different event proves that the prohibited branch was energized?

## 3. Repairing the wrong boundary

1. Load **Faulty patch: target only** and compile it.
2. Run **Upstream-close counterexample** again.
3. Inspect why checking only whether the requested target is out of service does
   not mediate an upstream operation that energizes an already-closed branch.

**Design question:** Which transitions can newly energize an unavailable section?

## 4. Safety and service together

1. Load **Faulty patch: deny every close**, compile, and run
   **Legitimate healthy restoration**.
2. Observe that avoiding the fault is insufficient when S1 and S2 remain unserved.
3. Load **Repair: resulting topology**, compile, and run both
   **Upstream-close counterexample** and **Legitimate healthy restoration**.

The mission strip reports safety, protection, required service, and sustained
service separately. A good repair must satisfy all four.

## 5. Generalization

With **Repair: resulting topology** active, run **Round 2: fault moved to S2**.
The healthy set changes to S1 and S3. The same controller should use the supplied
out-of-service mask rather than a hardcoded branch name.

**Closing question:** What assumptions are encoded in the repair, and which are
provided by trusted runtime state?

## Optional evidence handoff

Open **Evidence**, select the decisive event, and export the run. A defensible
claim should bind the request, controller build and source hash, decision,
reported position, electrical measurement, protection state, and mission result.
