# HW4 workflow: can you get the robot to stop at the dock?

This is the course's small, one-dimensional Python robot. It lets you follow a complete test: choose an input, run the model, check a requirement, and inspect what happened. The browser uses the same Python engine as the commands below. You do not need Gazebo, a physical robot, a CTF account, or a paid AI tool.

## Start the model

Use a Mac or Linux terminal with Python 3.12. The pinned packages are in `requirements-tooling.txt`. Get the starter from the class repository:

```sh
git pull
cd labs/robot-docking-hw4
sh ./setup.sh
sh ./launch.sh
```

Run `git pull` from your existing `cs6494-fall2026-students` checkout. If you do not have a checkout yet, clone `https://github.com/iotrustlab-teaching/cs6494-fall2026-students.git` once, then enter `cs6494-fall2026-students/labs/robot-docking-hw4`. If you received the ZIP instead, use its extracted folder:

```sh
cd HW4_Robot_Docking_Student_Starter
sh ./setup.sh
sh ./launch.sh
```

Open the local URL printed by `launch.sh` (normally `http://127.0.0.1:8765/`). Keep that terminal open. If the port is busy, use `HW4_PORT=8766 sh ./launch.sh` and open the printed URL. Setup needs access to the Python package index once; subsequent runs are local. Commands below use `.venv/bin/python`. If you have an instructor-provided environment with the pinned packages, `HW4_PYTHON=/path/to/python sh ./launch.sh` selects it. The starter has been checked on macOS and Linux with Python 3.12; a Windows route has not yet been qualified. Contact the course staff if this route does not work for you.

## Understand one run

The dock is at position 0 m. Every fresh run starts the robot at position −3 m and speed 0. At each 0.05 s model step, `controller_command()` sees `observed_remaining = max(0, −position)` and commands the cruise speed or zero. This ideal observation stops at zero after the robot passes the dock. The robot still has momentum after a zero command.

The requirement checker uses the model's reference position and speed. Its `e` signal is **absolute distance from the dock**, `abs(position)`; it is not the controller's observation. The checker looks at eight samples at whole seconds 0–7. Lines between displayed dots help you see motion but are not checked as continuous-time behavior.

| Requirement | What the samples must show | Where to look |
| --- | --- | --- |
| Get there and stay there | Start at or inside 0.5 m at some second 0–5, then stay inside for the next two one-second samples. The check needs samples through second 7. | `service.pass`, `service.margin_m`, `service.first_window_start_s` |
| Move slowly inside | At each checked second 0–5, if `e <= 0.5 m`, speed must be `<= 0.2 m/s`. | `safety.pass`, `safety.exercised`, `safety.robustness_normalized`, `safety.too_fast_samples_s` |

Exactly 0.5 m is inside, and exactly 0.2 m/s is allowed. A robot that never enters the region at checked seconds 0–5 gets a logical **PASS** for the conditional speed rule and `antecedent NOT EXERCISED` for coverage. That does not mean it completed docking. A displayed speed score of zero also needs the direct Boolean result: at `e = 0.5 m` and speed `0.2001 m/s`, the speed rule fails even though the normalized score can be zero. The service margin is in metres; the speed score is dimensionless. The two checks have different time windows, and neither checks every 0.05 s state.

Find four code locations: `controller_command()` in `model.py`, the velocity/position update in `model.py`, `signals()` in `reference_spec.py`, and the search adapter and fixed speed objective in `hw4_core.py`. The reference formula is readable. This is an open-book exercise about interpreting and testing it, not guessing a hidden string.

## Know which input you are changing

| Name | Units and role | When you change it |
| --- | --- | --- |
| **Braking strength** (`braking_m_s2`) | m/s²; the scenario's maximum deceleration, varied by search. This is model variation, not an implemented attacker command. | Changed-input run and search. |
| **Brake-trigger distance** (`brake_at_m`) | Metres; the controller setting in `policy.json` that decides when to command zero. Its allowed range is 0.3–1.5 m. | Policy retest, after search and replay. |

The supplied starting policy is `{"brake_at_m": 0.8}`. Keep or restore that value for the baseline, changed-input comparison, and search. Change only `STUDENT_FORMULA` in `student_spec.py` for the formula exercise. Keep `reference_spec.py`, the model, requirements, thresholds, signal meanings, and sample schedule fixed when comparing policies. Do not edit a saved run and call it a new execution.

## Monday: baseline, requirement, changed input

First, predict what the robot will do. In the browser, select **Baseline** and click **Run a fresh model execution**. Watch the robot with **Play animation**, step between the eight monitored samples, or click a plot dot. The command and actual speed shown at the same time can differ. Playback and scrubbing only move through this recorded run; they do not execute the model again. Inspect the eight sampled rows, then reveal the RTAMT checks and download the JSON. The terminal equivalent is:

```sh
.venv/bin/python hw4.py run --out runs/my_baseline.json
```

Translate this **one English requirement** into STL: “At some whole-second sample from second 0 through second 5, the robot must be at or within 0.5 m of the dock, and it must remain at or within 0.5 m at the next two whole-second samples.” Here `e` is absolute distance in metres, and `e = 0.5` counts as inside. A start at second 5 needs samples at seconds 5, 6, and 7. Write a first formula and a one-sentence explanation of what its time bounds mean before running the checker. The starter's `STUDENT_FORMULA` checks only one visit, so edit that variable in `student_spec.py` to express the full requirement. Check it:

```sh
.venv/bin/python hw4.py check-spec --out runs/my_formula_check.json
```

The starter formula deliberately gives a **DIFF** and exit status **1**. That means the exercise is incomplete, not that setup failed. After you edit, `MATCH` for the supplied cases and exit status 0 mean those examples agree; they do not prove equivalence on every possible trace. An invalid formula or invalid fixture reports `ERROR` and exits 2. The supplied cases include a brief visit, a three-sample stay, no entry, and the exact 0.5 m boundary. Look at margins as well as PASS/FAIL.

You may ask an AI tool to propose a formula, critique yours, or suggest an edge-case trace **after** your own first attempt. Treat its output as a candidate, not an answer: compare its meaning with the English sentence and test it with `check-spec`. Look especially at whether it requires three samples, allows the 0.5 m boundary, and has evidence through second 7. AI is optional; you can do the same critique yourself or with a classmate. In your explanation, briefly state what the critique found, how you checked it, and any substantive AI help you used. Do not submit a chat transcript or confidential course/testbed material.

Create one extra test. Copy `student_fixture_template.json` to `runs/my_authored_fixture.json`; its only field is `distance_m`, an array of **eight finite, nonnegative metre values** for seconds 0–7 in order. Predict the result and service margin before running:

```sh
.venv/bin/python hw4.py check-spec --trace-file runs/my_authored_fixture.json \
  --out runs/my_formula_check.json
```

This replaces the earlier formula-check report with one containing the supplied cases **and** your authored case. An authored fixture tests the monitor; it does not run the robot. Alternatively, write a precise boundary argument in your explanation: give eight distances for seconds 0–7, predict the verdict, and calculate the margin as the largest of the six three-sample window minima of `0.5 − e`. No fixture file is needed for that option.

Next, hold the 0.8 m policy fixed and change only scenario **braking strength** from 0.5 to 0.6 m/s². In the browser choose **Case A**, run and download, or use:

```sh
.venv/bin/python hw4.py run --braking 0.6 --out runs/my_changed_input.json
.venv/bin/python hw4.py compare-runs runs/my_baseline.json \
  runs/my_changed_input.json --out runs/my_input_comparison.json
```

Point to a sampled time that helps explain what changed. `compare-runs` checks both saved model runs and names the changed input. Keep both run JSON files and the comparison.

## Wednesday: search, replay, change the policy

The search has an outer loop: choose a **braking strength** `b`, run the model with the original policy, and score the resulting trace with the **fixed speed rule**. It does not optimize your student service formula. In short, `J(b)` is the speed-rule score of the new run generated using `b`; lower is more adverse. You still need to inspect docking service separately. A seed makes an experiment repeatable; a budget limits objective evaluations. The two strategies need not try the same points.

Keep `policy.json` at 0.8 m. Use the released matched comparison (one experiment, not an optimizer benchmark):

```sh
.venv/bin/python hw4.py compare-search --seed 7 --budget 12 \
  --min-braking 0.6 --max-braking 1.6 --out runs/my_search_comparison.json
```

Inspect `random.evaluations` and `guided.evaluations`. Each entry records a model-generated case, its speed score, direct speed-rule Boolean, and docking result. Check `actual_evaluations` for each strategy; the code also reruns evaluated cases to verify their saved records, so this count means **search-objective evaluations**, not every internal verification run. The selected case is the lowest-score case, with a direct Boolean failure preferred at a zero-score tie. Do not infer that one optimizer is generally better from one seed.

Choose **one of the comparison's selected cases**. This command exports that exact embedded run; it does not start a second search:

```sh
.venv/bin/python hw4.py select-case runs/my_search_comparison.json \
  --strategy guided --out runs/my_selected_case.json
.venv/bin/python hw4.py replay runs/my_selected_case.json \
  --out runs/my_replay.json
```

You may use `--strategy random` instead. The exported run ID must match the chosen strategy's `selected_run.run_id` in the comparison. `replay` reruns the saved scenario with its **original saved policy** and checks that the result matches; it is not a redraw of stored points. If **neither** strategy has a case with `safety.pass = false` (check the direct Boolean, not merely whether a score is negative), use `calibration/calibration_adverse_b1p0.json` instead. It is staff supplied, not your discovery. Replay it with the same `replay` command and name it as your adverse case. A failed small search does not prove the policy safe.

Before editing the policy, predict how moving the brake-trigger distance might affect both speed and docking. Change only `brake_at_m` in `policy.json`, within 0.3–1.5 m. Retest **three scenarios** with the new policy: your selected adverse case **or** the staff calibration case, plus the supplied normal and additional cases. The last two originals are `calibration/normal_s1p5_b1p5.json` and `calibration/additional_b1p6.json`.

```sh
.venv/bin/python hw4.py retest runs/my_selected_case.json \
  --out runs/my_retest_adverse.json
.venv/bin/python hw4.py retest calibration/normal_s1p5_b1p5.json \
  --out runs/my_retest_normal.json
.venv/bin/python hw4.py retest calibration/additional_b1p6.json \
  --out runs/my_retest_additional.json
```

If you used the supplied adverse calibration case, replace the first input path with `calibration/calibration_adverse_b1p0.json`. Do **not** add a fourth required adverse retest. `retest` holds each saved scenario fixed and runs the newly edited policy; its JSON names the original run ID. Compare the old and new Boolean results, speed scores, and docking margins. A change that helps one case but hurts another is useful to discuss. No setting is assumed to fix every possible scenario.

## Output checklist for one ZIP

Keep the following in your submission ZIP. The commands above create files under `runs/`; a browser download is equivalent if it contains the same fresh run. You may choose different filenames if their purposes remain clear. Run IDs are already in the JSON; you need not copy every ID by hand.

| Purpose | File to keep | Produced by |
| --- | --- | --- |
| Your edits | `student_spec.py`, `policy.json` | Your formula and brake-trigger-distance edits |
| Requirement check | `runs/my_formula_check.json` | `check-spec --out` (with your authored fixture if used) |
| Extra monitor test | `runs/my_authored_fixture.json` **or** eight values and hand calculation in your explanation | Your authored fixture or boundary argument |
| First two model runs | `runs/my_baseline.json`, `runs/my_changed_input.json` | Two `run` commands or browser downloads |
| Input comparison | `runs/my_input_comparison.json` | `compare-runs` |
| Search histories | `runs/my_search_comparison.json` | `compare-search` |
| Chosen adverse case | `runs/my_selected_case.json` if found; otherwise name the supplied calibration case in your explanation | `select-case` or supplied `calibration/calibration_adverse_b1p0.json` |
| Reproduction | `runs/my_replay.json` | `replay` of that same adverse case |
| Policy tests | `runs/my_retest_adverse.json`, `runs/my_retest_normal.json`, `runs/my_retest_additional.json` | Three `retest` commands |
| Explanation, at most two pages | PDF or Markdown file | Your map, three short prediction/check notes, before/after table, what you learned, and what remains untested |

Do not include `.venv`, installed packages, or regenerated staff calibration files. The class worksheets are guides to this same homework, not separate submissions. Canvas is the source for the assignment's due date and submission settings when it is published. Until then, this repository is practice material, not a new deadline.
