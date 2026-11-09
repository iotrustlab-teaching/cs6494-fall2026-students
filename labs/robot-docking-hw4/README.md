# CS 6494 HW4 robot docking starter

Pull the class repository and enter `labs/robot-docking-hw4`, or use the extracted starter ZIP. Start with [HW4_WORKFLOW.md](HW4_WORKFLOW.md), then use [Monday's worksheet](MONDAY_CLASS_WORKSHEET.md) and [Wednesday's worksheet](WEDNESDAY_CLASS_WORKSHEET.md). The browser page opens through `sh ./launch.sh`; it does not work as a standalone `file://` page because its runs come from the local Python engine. Check Canvas for the current assignment status, due date, and submission settings. Keep your edited files and generated runs in your own checkout and submit them through Canvas.

This model is a course-authored one-dimensional simulation. Each run resets and generates a new trace. RTAMT computes STL robustness from the eight whole-second samples; an exact sampled check supplies the inclusive-boundary PASS/FAIL result. PSY-TaLiRo uses RTAMT's fixed speed-rule score to search braking inputs. `student_fixture_template.json` is for hand-authored monitor examples only; editing it does not run the robot. No Gazebo, autopilot, network account, or hardware is used.

The browser now follows the four HW4 questions. It runs and verifies the **Part 1 baseline/changed-input comparison**, visualizes any saved run, and re-executes a **Part 3 selected case**. The editable STL formula check, PSY-TaLiRo search, and three policy retests still use the Python commands in [HW4_WORKFLOW.md](HW4_WORKFLOW.md); the browser labels those steps instead of implying that its Run button performs them.

After a run, **Play animation**, sample stepping, plot dots, and the time scrubber only change which recorded state you see; they do not execute the model again. **Run a fresh model execution** and **Replay selected file** do execute Python. The robot drawing is illustrative; its center dot is the modeled point position.

The `calibration/` files in this starter are labeled staff-generated model runs. They are fallback examples, not runs discovered by your search.
