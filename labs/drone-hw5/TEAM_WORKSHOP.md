# HW5 / CTF2 team workshop: plan one drone test

Work with your **CTF2 planning team of 5–6**. Today you will choose a test and decide what evidence would answer it. **The local Docker simulator runner is not released yet; do not install or fly anything for this activity.** We will walk through the starter code in class when it is ready. Canvas will give the final HW5 submission and team rules.

The supplied software mission asks a drone to follow a route. A GPS edit can make the position reported to its flight controller differ from its actual position. A watchdog may notice and request a response. Your test must examine both protection and whether the drone can still complete an ordinary mission.

## Decide together

1. **Attack hypothesis:** Complete: “If reported GPS position changes **_____** starting **_____**, we expect the actual route to **_____** because **_____**.” Choose a position step or gradual change; propose timing, direction, and size within the starter's eventual bounds. These are predictions, not results.
2. **One watchdog change:** What reading should it check, and what should it request when suspicious? Choose one change to the supplied watchdog. Name an ordinary-flight condition that could cause a false alarm.
3. **Evidence:** Decide how you will compare *reported GPS position* with *simulator actual position*. Record a requested BRAKE or other action separately from the flight controller's **actual mode**.

## Four flights to run after the starter is released

Use the same mission and simulator version; reset before each flight. Runs 2 and 3 must use **identical attack settings**.

| Run | GPS edit | Watchdog | Question |
|---|---|---|---|
| 1 | None | Supplied | What does normal flight look like? |
| 2 | Chosen edit | Supplied | What changed under the attack? |
| 3 | **Same edit** | Your revision | Did the revision help? |
| 4 | None | Your revision | Did it disrupt normal flight? |

Keep each run ID, actual route/mission result, watchdog event, and actual controller mode. Do not fill in outcomes before running the released package.

## Assign owners before leaving

- **Setup owner and backup:** Check a team laptop and Docker access when instructions arrive; no physical drone or public system is in scope.
- **Code owner:** Bring the proposed GPS settings and watchdog change to the walkthrough.
- **Evidence owner:** Keep four receipts and the comparison table. Everyone should be able to explain the result.

Be ready to share your attack hypothesis, watchdog idea, possible false alarm, and the evidence that would show whether the drone *actually* changed course.
