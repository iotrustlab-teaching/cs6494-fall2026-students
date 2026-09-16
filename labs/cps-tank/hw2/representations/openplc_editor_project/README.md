# Optional OpenPLC Editor project

This folder is a read-only, student-facing view of the HW2 controller. In
OpenPLC Editor v3, choose **Open Project** and select this entire folder. The
Editor should display the `HW2TankController` program, its variable interface,
and its Structured Text body.

Compare the project with `../controller.st` and locate:

- the reported level input;
- the retained inlet-valve command;
- the low and high thresholds; and
- the middle band in which the command keeps its previous value.

This project is for structural exploration only. The PLCopen XML emitted for
the Editor does not retain the located ST `AT` bindings (`%MD0` and `%QX0.0`).
The required lab therefore mounts `../controller.st` into the OpenPLC Runtime.
Opening this project does not deploy or execute it and is not runtime evidence.
