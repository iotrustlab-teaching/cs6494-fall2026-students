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

(* Vulnerable: present current does not predict the proposed topology. *)
CloseInterlock :=
  CloseRequested
  AND NOT TripLatched
  AND (PresentCurrent_dA < CurrentLimit_dA);
END_FUNCTION
