# Wednesday, November 11 — search for a case, replay it, and try a change

Continue in the same starter folder. Use [HW4_WORKFLOW.md](HW4_WORKFLOW.md) for the exact commands and output checklist. This is HW4 progress, not a second lab.

Last class we scored one trace. Today the tester chooses a **braking-strength** value, runs the robot under the original 0.8 m policy, and scores the new trace. Each search entry is a complete model execution. The fixed **speed rule** supplies the search score; docking is checked separately. A lower score is more adverse, but the direct Boolean result decides a zero-score boundary.

In class we will compare this small search with [PGFuzz](https://www.ndss-symposium.org/ndss-paper/pgfuzz-policy-guided-fuzzing-for-robotic-vehicles/), which also asks how to choose useful tests in a larger robotic system. You do not run PGFuzz for this homework.

## 1. Predict what the search can change

Open `hw4_core.py` and find the `adapter()` and `rtamt.parse_discrete(SAFETY_FORMULA)` call. Before running search, write a sentence: what varies, what stays fixed, and why might that affect the speed rule? Keep `policy.json` at its original `brake_at_m = 0.8 m` until after replay.

```sh
.venv/bin/python hw4.py compare-search --seed 7 --budget 12 \
  --min-braking 0.6 --max-braking 1.6 --out runs/my_search_comparison.json
```

The varied **braking strength** is in m/s². It is a scenario-model parameter, not an attacker command. `brake_at_m` is a different value: the controller's brake-trigger distance in metres. The command runs random and guided PSY-TaLiRo searches with the same bounds, seed, and budget. They need not try the same inputs.

1. In the JSON, check `random.actual_evaluations` and `guided.actual_evaluations` and the length of each `evaluations` list. Each should represent 12 search-objective evaluations. The program also performs verification reruns; these are counted separately.
2. Compare the two selected cases' braking strengths, speed-rule Boolean results, scores, and docking results. A score is not itself the complete Boolean verdict at an exact boundary.
3. This one comparison is not evidence that one optimizer is generally better.

## 2. Reproduce the case you chose

Look at both **selected runs**. If one or both have `safety.pass = false`, choose a failing one. The command below chooses guided **only if guided failed**; use `--strategy random` if only random failed. Export that exact embedded case, then replay it:

```sh
.venv/bin/python hw4.py select-case runs/my_search_comparison.json \
  --strategy guided --out runs/my_selected_case.json
.venv/bin/python hw4.py replay runs/my_selected_case.json \
  --out runs/my_replay.json
```

Confirm the exported run ID matches that strategy's `selected_run.run_id` in the comparison. The replay runs the model again with the **saved original policy** and checks the result. Point to the sampled second that explains the speed-rule result, and check whether docking worked too.

If **neither selected run** has `safety.pass = false`, use `calibration/calibration_adverse_b1p0.json` as the adverse case instead. It is a staff-supplied model run, not your search discovery. Replay that file and name it clearly. Do not decide fallback from “no negative score” alone: a zero score can accompany a direct Boolean failure. A small search with no violation does not prove safety.

## 3. Predict a policy change, then test exactly three cases

Before editing, write what you expect a changed brake-trigger distance to do to **both** speed and docking. What result would make you reconsider? Now change only `brake_at_m` in `policy.json` within 0.3–1.5 m. Keep the requirements and model unchanged.

Run one fresh retest for each of these three saved scenarios:

1. **Adverse:** `runs/my_selected_case.json` if your search found a failure, **or** `calibration/calibration_adverse_b1p0.json` if you used the fallback.
2. **Normal:** `calibration/normal_s1p5_b1p5.json` (cruise 1.5 m/s; braking 1.5 m/s²).
3. **Additional:** `calibration/additional_b1p6.json` (cruise 1.2 m/s; braking 1.6 m/s²).

The supplied calibration runs all used the original 0.8 m brake point. Each retest changes the policy while holding that file's own scenario fixed.

```sh
.venv/bin/python hw4.py retest runs/my_selected_case.json \
  --out runs/my_retest_adverse.json
.venv/bin/python hw4.py retest calibration/normal_s1p5_b1p5.json \
  --out runs/my_retest_normal.json
.venv/bin/python hw4.py retest calibration/additional_b1p6.json \
  --out runs/my_retest_additional.json
```

Replace the first input path with the supplied adverse calibration file if that was your case. Calibration is **not** a fourth required retest when you used a selected search case. Each `retest` holds its scenario fixed and uses your edited policy. Make a short before/after table with the speed-rule Boolean, normalized speed score, docking result/margin, and whether the speed-rule antecedent was exercised. The JSON carries run IDs; refer to filenames or IDs rather than copying every field by hand.

## Discuss and save

Did your change help the adverse case? Did the normal mission still dock? Did the additional case reveal a tradeoff? Keep a wrong prediction and explain what the run showed. An honest partial result can be good work; no single setting is assumed to fix every scenario.

Save the search comparison, selected case or named calibration source, replay output, edited `policy.json`, and three retest JSON files. All are part of the same HW4 ZIP and at-most-two-page explanation.

The [ROCAS](https://arxiv.org/html/2409.07774v2) research case asks a follow-up question: once you have found a failure, which controlled changes help locate its cause? Holding scenario braking fixed while changing `brake_at_m` is a small analogy. This homework does not implement ROCAS or show what a real robot would do.
