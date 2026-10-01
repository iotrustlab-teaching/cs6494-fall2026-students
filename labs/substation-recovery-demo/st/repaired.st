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
VAR
  ProjectedPositions : BYTE;
  EnergizedBranches : BYTE;
END_VAR

(* Repair: decide from the topology that would result after the request. *)
ProjectedPositions := ActualPositions OR TargetMask;

IF (ProjectedPositions AND 16#01) <> 0 THEN
  EnergizedBranches := ProjectedPositions AND 16#0E;
ELSE
  EnergizedBranches := 0;
END_IF;

CloseInterlock :=
  CloseRequested
  AND NOT TripLatched
  AND ((EnergizedBranches AND OutOfServiceMask) = 0);
END_FUNCTION
