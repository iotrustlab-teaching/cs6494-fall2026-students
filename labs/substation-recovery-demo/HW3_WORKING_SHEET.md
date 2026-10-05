# HW3 working sheet: From requirement to defensible guardrail

The in-browser **Finish HW3 submission** builder is the primary workflow. This
sheet is the printable/offline fallback when the hosted lab or browser storage
is unavailable. Work with a partner or trio during class, but write your own
answers. Canvas remains authoritative for the deadline and submission settings.

Submit one file named `HW3_<uNID>.pdf`. The narrative should remain compact;
controller source and captured-run identifiers may appear in an evidence
appendix. Label each result `TESTED`, `REPLAYED`, or `PROPOSED` accurately.

## Checkpoint A: Repair

Use the supplied `riverbend_substation_fds_excerpt.pdf` as the operating-source
artifact. Cite the applicable requirement ID and page. Treat its fictional
document metadata as provenance for this exercise, not as evidence about a real
utility.

### 1. Property and boundary

- Prohibited outcome:
- Useful operation that must remain possible:
- Source of the operating requirement:
- Enforcement boundary:

### 2. Counterexample

| Initial state | Request | Controller decision | First prohibited effect |
|---|---|---|---|
|  |  |  |  |

Which state dependency did the starter controller omit?

### 3. Repair

Paste the relevant logic, diff, or pseudocode. Explain why it enforces the
property rather than blocking only the observed request.

### 4. Two tests

| Request and state | Expected result | Observed, replayed, or proposed? | Evidence reference |
|---|---|---|---|
| Prohibited transition |  |  |  |
| Legitimate restoration |  |  |  |

Do not label a source inspection or captured replay as a newly tested repair.

## Checkpoint B: Assumption stress test

The last safe position report is now stale. The physical state changes before
the controller acts.

- Which assumption from Checkpoint A expired?
- Which evidence can no longer support your earlier conclusion?
- Where should freshness, versioning, or rechecking occur?
- Which positive-service test must still pass after the revision?

## Checkpoint C: Transfer

For the unfamiliar utility fragment supplied in class, identify:

- the safety or service property;
- the missing evidence;
- the likely enforcement point;
- the first assumption you would test.

Do not assume the fragment uses the substation's devices, protocol, or bitmask.
Transfer the reasoning method, not the reference implementation.

## Revised bounded claim

Complete this sentence in your own words:

> Under assumptions ______, evidence ______ supports the claim that ______.
> It does not establish ______.
