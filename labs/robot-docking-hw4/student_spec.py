"""Student-editable formula exercise. The fixed evaluator never imports this file.

Monday task: translate the English docking requirement in HW4_WORKFLOW.md into
STL. Extend the initial 'reach once' formula to require three consecutive
integer-second samples inside or at the 0.5 m boundary. The start window is
0–5 s, so a start at t=5 requires evidence through t=7.
"""

STUDENT_FORMULA = "eventually[0,5] (e <= 0.5)"
