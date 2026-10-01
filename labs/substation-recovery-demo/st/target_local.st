FUNCTION CloseInterlock : BOOL
VAR_INPUT
  CloseRequested : BOOL;
  ActualPositions : BYTE;
  TargetMask : BYTE;
  OutOfServiceMask : BYTE;
  TripLatched : BOOL;
  PresentCurrent_dA : UINT;
  CurrentLimit_dA : UINT;
END_VAR

(* Faulty patch: blocks only a command whose named target is out of service. *)
CloseInterlock :=
  CloseRequested
  AND NOT TripLatched
  AND ((TargetMask AND OutOfServiceMask) = 0)
  AND (PresentCurrent_dA < CurrentLimit_dA);
END_FUNCTION
