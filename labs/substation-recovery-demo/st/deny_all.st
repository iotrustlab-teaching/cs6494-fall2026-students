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

(* Faulty patch: safe from closing, but incapable of restoring service. *)
CloseInterlock := FALSE;
END_FUNCTION
