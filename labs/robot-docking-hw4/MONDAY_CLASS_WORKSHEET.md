# Monday, November 9 — run the robot and check what “dock” means

Use [HW4_WORKFLOW.md](HW4_WORKFLOW.md) for setup and file commands. Work with a partner and switch who operates after the first run. This is progress on HW4, not a second lab submission.

## First, find what runs

The robot starts 3 m left of the dock. The controller's initial brake-trigger distance is `brake_at_m = 0.8 m`. A zero command does not stop the robot instantly.

1. Find `controller_command()` in `model.py`. What distance does it see, and when does it command zero?
2. Find the velocity and position updates in `model.py`. Why can the robot keep moving after that command?
3. Find `signals()` in `reference_spec.py`. The checker uses `e = abs(position)`, the reference distance from the dock. How is that different from the controller's `observed_remaining` value?
4. On Wednesday, the adapter in `hw4_core.py` will connect a changed braking-strength input to a new model run and a speed-rule score.

Make a small sketch: scenario input → controller observation → command → motion → checked samples.

## 1. Predict, then run the baseline

We check only the samples at whole seconds. For **docking**, the robot must be at or inside 0.5 m for three consecutive one-second samples starting by second 5; this needs samples through 7. For **speed**, being inside at a checked second 0–5 requires speed at most 0.2 m/s. Exactly 0.5 m and exactly 0.2 m/s are allowed.

1. Before revealing results, guess whether the robot docks and whether it moves slowly at its checked inside samples. A wrong guess is fine; keep it to compare with the trace.
2. In the browser, choose **Baseline** → **Run a fresh model execution**. Look at the chart and eight sampled rows. Reveal the requirements and download the JSON. Terminal alternative: `.venv/bin/python hw4.py run --out runs/my_baseline.json`.
3. Point to one sampled time that helps explain a result. What did the robot do there?

The direct speed-rule Boolean and `antecedent EXERCISED/NOT EXERCISED` answer different questions. Never entering during seconds 0–5 can make the conditional speed rule true without completing docking.

## 2. Make the requirement say what you mean

Translate this sentence into STL: **“At some whole-second sample from 0 through 5, the robot is at or within 0.5 m of the dock and stays there for the next two whole-second samples.”** Here `e` is absolute distance from the dock, exactly 0.5 m counts, and a start at second 5 needs evidence through second 7. The starter `STUDENT_FORMULA` in `student_spec.py` checks for one visit. Before editing, write your first formula, explain its time bounds, and describe a trace that visits once but does not stay for three samples. The fixed formula in `reference_spec.py` is open for inspection; your job is to understand and test the rule.

1. Edit only `STUDENT_FORMULA` for three consecutive inside samples, starting at some second 0–5.
2. Run `.venv/bin/python hw4.py check-spec --out runs/my_formula_check.json`. A **DIFF** and exit status 1 are expected with the starter formula. After your edit, `MATCH` on the supplied examples is useful evidence, not proof for every possible trace. `ERROR` and exit status 2 mean the formula or input is invalid.
3. Explain the brief-visit and exact-boundary examples, including their margins.
4. Make **one** new test: either fill `student_fixture_template.json` with eight nonnegative distances for seconds 0–7 and run `check-spec --trace-file runs/my_authored_fixture.json --out runs/my_formula_check.json`, or write those eight distances and calculate the three-sample window margin by hand. Predict before checking. An invented fixture tests the monitor; it is not a fresh robot run.

Optional: after your own draft, ask an AI tool to critique the formula or suggest a boundary case. Check the suggestion against the sentence and `check-spec`; report what it got right or wrong and how you verified it. You can do the same check without AI. Do not submit a chat transcript.

## 3. Change an input and compare two runs

Keep `policy.json` at **0.8 m**. Predict what changing the scenario's **braking strength** from 0.5 to 0.6 m/s² might do. This is a model parameter, not the controller's brake-trigger distance.

1. In the browser, choose **Case A** → **Run a fresh model execution**, then download. Terminal alternative: `.venv/bin/python hw4.py run --braking 0.6 --out runs/my_changed_input.json`.
2. Compare the two sets of sampled distances and speeds. What changed, and what stayed fixed?
3. Save the comparison: `.venv/bin/python hw4.py compare-runs runs/my_baseline.json runs/my_changed_input.json --out runs/my_input_comparison.json`. Use your browser-download paths if you ran there.

## Leave with

Keep the two model-run JSON files, the input-comparison JSON, your edited `student_spec.py`, your formula-check JSON, and your extra monitor fixture or written boundary argument. Put your short prediction/check notes in the same HW4 explanation later; there is no separate class submission.

Before Wednesday, ask: last class we scored **one trace**. If we can choose an input and run again, which input should we try next? A larger robot has many candidates; [PGFuzz](https://www.ndss-symposium.org/ndss-paper/pgfuzz-policy-guided-fuzzing-for-robotic-vehicles/) is one research approach we will examine. You do not need to install it.

If your local setup is blocked, use a partner's or instructor's run for class reasoning and tell the staff. The independent homework runs still need a supported environment. Do not edit a saved sample and label it a new model run.
