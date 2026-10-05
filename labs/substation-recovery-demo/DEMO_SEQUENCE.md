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
3. Write or propose a repair before opening the instructor reveal. Specify one
   prohibited-transition test and one legitimate-service test.
4. Compile the student repair and run both tests. Record the result as
   **tested**, **replayed**, or **proposed** accurately.
5. Only after students commit, open **Instructor reveal: reference build** and
   load **Repair: resulting topology** for comparison.

The mission strip reports safety, protection, required service, and sustained
service separately. A good repair must satisfy all four.

## 5. Generalization

With **Repair: resulting topology** active, run **Round 2: fault moved to S2**.
The healthy set changes to S1 and S3. The same controller should use the supplied
out-of-service mask rather than a hardcoded branch name.

**Closing question:** What assumptions are encoded in the repair, and which are
provided by trusted runtime state?

## Submission handoff

Open **HW3 submission** in the top bar after the regression work. The lab moves
into a full-page workflow that presents one of the six guided checkpoints at a
time. Capture the active compiled repair and continue through Review. Completed
regressions are attached to the draft automatically; a `TESTED` label is
rejected if its run used a different build from the captured repair. Choose
**Create submission PDF** and save `HW3_<uNID>.pdf` for Canvas. The raw JSON
export remains optional.

## HW3 checkpoints

- **Repair:** Complete steps 1-4 and record the property, counterexample,
  control, negative test, positive-service test, and bounded claim in the
  browser submission builder. Use
  [HW3_WORKING_SHEET.md](HW3_WORKING_SHEET.md) only as a fallback.
- **Assumption stress test:** Revisit the claim when the position report may be
  stale. Identify the failed inference and where rechecking belongs.
- **Transfer:** Apply the same argument structure to an unfamiliar,
  protocol-neutral utility fragment. Do not reuse the substation answer.

CTF1 uses unfamiliar water-treatment, water-distribution, and hydro/power
utility families under a common evidence contract. This activity teaches the
reasoning grammar without disclosing those scenario instances.
