# HW2 grading rubric

Total: 100 points. Grade the reasoning and evidence, not command memorization.

| Area | Points | Full-credit evidence |
|---|---:|---|
| A. Program structure and realizability | 15 | Correct observation, branches, retained state, output, feasible path, physical-realizability assumptions, and one reason the violation could remain unreachable |
| B. PLC/tag/network authority | 20 | Correct concept-to-ST-to-address map, owner/authority labels, data-plane/program-plane distinction, and separation of a valid write from an authorized or safe outcome |
| C. Prediction and causal execution | 20 | Prediction and distinguishing evidence precede the run; explanation follows operation → input → branch → command → process |
| D. Bounded search and oracle | 20 | Justified finite search surface, correct process-truth oracle, checker critique or secondary property, bounded counterexample interpretation, and negative-result limitation |
| E. Layered evidence-backed claim | 20 | Separates program capability, runtime observation, network/authority, physical consequence, and verdict; matches minimum evidence to each; states fidelity and claim limits |
| Recovery and scope discipline | 5 | Reset/release confirmed; no out-of-bounds target or unsupported evidence claim |

## Performance anchors

- **Excellent (90–100):** cross-layer reasoning is precise; each claim is
  matched to evidence and limitations.
- **Competent (75–89):** main causal chain and property are correct; small
  mapping or evidence-boundary errors do not alter the conclusion.
- **Developing (60–74):** execution completed but reasoning collapses reported
  state into process truth, or treats an accepted write as physical proof.
- **Insufficient (<60):** mostly command output, an unbounded safety claim, or
  no defensible causal/evidence chain.

## Safety and integrity handling

Do not reward probing outside the assigned realization, arbitrary address
entry, credential sharing, or program upload. Route suspected boundary
violations to course policy rather than improvising a technical penalty.

## How reasoning is graded

The rubric intentionally names the required claim layers without supplying a
completed interpretation. Full credit depends on citing exact evidence from
your own run, explaining what it establishes, and naming a limit or stronger
unsupported claim. Raw command output, copied reference prose, or a verdict
without that reasoning does not satisfy the rubric. Alternative evidence
selections can earn full credit when their sufficiency and limitations are
defended.
