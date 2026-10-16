"""Explicit synthetic alignment in shared local ENU meters and degrees."""

from dataclasses import dataclass
from math import hypot

from docking.states.docking_controller import finite_number, valid_ns, yaw_difference
from docking.states import DockingInput


@dataclass(frozen=True)
class LocalPosition:
    x_m: float
    y_m: float
    origin_id: str
    frame: str = 'local_enu'
    yaw_deg: float = 0.0


@dataclass(frozen=True)
class AlignmentResult:
    valid: bool
    timestamp_ns: int | None = None
    x_error_m: float | None = None
    y_error_m: float | None = None
    yaw_error_deg: float | None = None
    horizontal_error_m: float | None = None
    reason: str = ''
    source_id: str = 'synthetic_alignment'
    synthetic: bool = True
    frame: str = 'local_enu'

    def to_docking_input(self):
        return DockingInput(
            alignment_valid=self.valid,
            alignment_timestamp_ns=self.timestamp_ns,
            x_error_m=self.x_error_m, y_error_m=self.y_error_m,
            yaw_error_deg=self.yaw_error_deg, alignment_source_id=self.source_id,
        )


def calculate_alignment(pad: LocalPosition | None, vehicle: LocalPosition | None,
                        timestamp_ns: int | None) -> AlignmentResult:
    """Pad minus vehicle offsets; the controller validates observation freshness."""
    if not valid_ns(timestamp_ns):
        return AlignmentResult(False, reason='invalid_timestamp')
    if not isinstance(pad, LocalPosition) or not isinstance(vehicle, LocalPosition):
        return AlignmentResult(False, timestamp_ns, reason='missing_position')
    if pad.frame != 'local_enu' or vehicle.frame != 'local_enu':
        return AlignmentResult(False, timestamp_ns, reason='invalid_frame')
    if not isinstance(pad.origin_id, str) or not pad.origin_id or pad.origin_id != vehicle.origin_id:
        return AlignmentResult(False, timestamp_ns, reason='origin_mismatch')
    values = (pad.x_m, pad.y_m, vehicle.x_m, vehicle.y_m,
              pad.yaw_deg, vehicle.yaw_deg)
    if not all(finite_number(value) for value in values):
        return AlignmentResult(False, timestamp_ns, reason='invalid_position')
    x, y = pad.x_m - vehicle.x_m, pad.y_m - vehicle.y_m
    yaw = pad.yaw_deg - vehicle.yaw_deg
    distance = hypot(x, y)
    if not all(finite_number(value) for value in (x, y, distance, yaw)):
        return AlignmentResult(False, timestamp_ns, reason='alignment_overflow')
    return AlignmentResult(True, timestamp_ns, x, y, yaw_difference(yaw, 0),
                           distance, 'synthetic_alignment')
