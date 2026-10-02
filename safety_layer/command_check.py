"""The second safety check: looking at one actual order.

The first check (safety_policy.py) answers "is tracking allowed right now?"
This one answers "is THIS specific order safe to send?" -- for example,
"fly to 200 metres east at 40 metres up, going 9 m/s".

The team's plan (Section 3, step 7) says safety must not just say no. If an
order is unsafe we hand back a SAFE REPLACEMENT order, because doing nothing
would leave the drone chasing its old target.
"""

import math
from dataclasses import dataclass, replace
from typing import Optional, Tuple

from safety_layer import config
from safety_layer.safety_policy import SafetyAssessment


# Which order needs which permission from the first check.
KIND_TO_ACTION = {
    "takeoff": "launch",
    "track": "tracking",
    "dock_approach": "approach",
    "descend": "descent",
    "hover": "hold",
    "hold": "hold",
    "land": "hold",            # landing is how we stop; the hold rules cover it
    "emergency_land": "hold",
    "arm": "launch",
    "disarm": "hold",
}


@dataclass(frozen=True)
class Command:
    """One order for the drone."""

    command_id: str
    kind: str                           # "takeoff", "track", "descend", ...
    x_m: float = 0.0                    # east
    y_m: float = 0.0                    # north
    z_m: float = 0.0                    # up
    horizontal_speed_mps: float = 0.0
    vertical_speed_mps: float = 0.0
    yaw_rate_dps: float = 0.0
    issued_ns: int = 0                  # when it was created
    source: str = "unknown"             # who asked for it
    reason: Optional[str] = None


@dataclass(frozen=True)
class CommandDecision:
    """Safety's answer about one order."""

    allowed: bool                       # True = send the order as-is
    command: Command                    # the order to send (original or replacement)
    reasons: Tuple[str, ...] = ()       # short words explaining any problem
    timestamp_ns: int = 0

    @property
    def replaced(self) -> bool:
        """True if we swapped in a different order."""
        return not self.allowed


def _hold_command(original: Command, now_ns: int) -> Command:
    """A safe 'stop and stay put' order to use instead of a bad one."""
    return replace(
        original,
        command_id=f"{original.command_id}-safety-hold",
        kind="hold",
        horizontal_speed_mps=0.0,
        vertical_speed_mps=0.0,
        yaw_rate_dps=0.0,
        issued_ns=now_ns,
        source="safety",
        reason="safety_hold",
    )


def _land_command(original: Command, now_ns: int) -> Command:
    """An emergency 'come down right here' order."""
    return replace(
        original,
        command_id=f"{original.command_id}-safety-land",
        kind="emergency_land",
        z_m=0.0,
        horizontal_speed_mps=0.0,
        vertical_speed_mps=config.MAX_VERTICAL_SPEED_MPS,
        yaw_rate_dps=0.0,
        issued_ns=now_ns,
        source="safety",
        reason="emergency_land",
    )


def check_command(
    command: Command, assessment: SafetyAssessment, now_ns: int
) -> CommandDecision:
    """Check one order and return it, or a safe replacement.

    command:    the order someone wants to send
    assessment: what the first safety check already decided this tick
    now_ns:     the current pretend time
    """
    problems = []

    # 1. An emergency beats everything: come down now.
    if assessment.emergency:
        return CommandDecision(
            allowed=False,
            command=_land_command(command, now_ns),
            reasons=("emergency",) + assessment.reasons,
            timestamp_ns=now_ns,
        )

    # 2. Is the order too old? Orders only last a fifth of a second, so a
    #    stale one might be based on information that has since changed.
    age_ns = now_ns - command.issued_ns
    if age_ns > config.COMMAND_VALIDITY_S * config.NS_PER_S or age_ns < 0:
        problems.append("command_expired")

    # 3. Is this kind of action even allowed right now?
    action = KIND_TO_ACTION.get(command.kind)
    if action is None:
        problems.append("unknown_command_kind")
    elif not assessment.allows(action):
        problems.append("action_not_permitted")

    # 4. Is the destination inside the invisible fence?
    distance_from_pad = math.hypot(command.x_m, command.y_m)
    if distance_from_pad > config.GEOFENCE_RADIUS_M:
        problems.append("geofence_breach")

    # 5. Is it trying to fly too high?
    if command.z_m > config.ALTITUDE_CEILING_M:
        problems.append("altitude_ceiling")

    # 6. Is it going too fast?
    if command.horizontal_speed_mps > config.MAX_HORIZONTAL_SPEED_MPS:
        problems.append("horizontal_speed_limit")
    if command.vertical_speed_mps > config.MAX_VERTICAL_SPEED_MPS:
        problems.append("vertical_speed_limit")
    if command.yaw_rate_dps > config.MAX_YAW_RATE_DPS:
        problems.append("yaw_rate_limit")

    # Anything wrong? Send a "stop and stay put" order instead.
    if problems:
        return CommandDecision(
            allowed=False,
            command=_hold_command(command, now_ns),
            reasons=tuple(dict.fromkeys(problems)),
            timestamp_ns=now_ns,
        )

    # All good: send the original order unchanged.
    return CommandDecision(allowed=True, command=command, timestamp_ns=now_ns)
