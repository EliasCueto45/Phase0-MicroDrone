# State machine code: picks the next state based on the current state and the observation.
# It only decides the state and reason; run_loop.py acts on the chosen state.

from enum import Enum

class State(Enum):
    IDLE = "IDLE"
    TRACKING = "TRACKING"
    HOVERING = "HOVERING"
    DOCKING_INIT = "DOCKING_INIT"
    DOCKING_APPROACH = "DOCKING_APPROACH"
    DOCKED = "DOCKED"
    ABORT = "ABORT"
    EMERGENCY_LAND = "EMERGENCY_LAND"

AIRBORNE = {
    State.TRACKING,
    State.HOVERING,
    State.DOCKING_INIT,
    State.DOCKING_APPROACH,
    State.ABORT
}

def is_airborne(state: State) -> bool:
    return state in AIRBORNE

def is_safe(safety: dict) -> bool:
    return (safety.get("people_nearby") is False
        and safety.get("cart_moving") is False
        and safety.get("weather") == "clear"
        and safety.get("camera_ok") is True
        and safety.get("comm_ok") is True)


# The observation is a dictionary in the team's shared JSON format
def step(state: State, observation: dict) -> tuple[State, str | None]:
    bird = observation.get("bird") or {}
    battery = observation.get("battery") or {}
    safety = observation.get("safety") or {}
    docking = observation.get("docking") or {}

    bird_seen = bird.get("detected") is True
    safe = is_safe(safety)
    should_dock = docking.get("should_dock") is True
    percent = battery.get("percent") or 0

    match state:
        # Idle state
        # Grounded at the dock, so return requests (should_dock) are ignored.
        # A launch goes through HOVERING before TRACKING (INTEGRATION_README.md section 2).
        case State.IDLE:
            if bird_seen and safe:
                return State.HOVERING, "Bird detected"
        # Tracking state
        case State.TRACKING:
            if should_dock:
                return State.DOCKING_INIT, "Should dock"
            if not safe:
                return State.HOVERING, "Not safe"
            if not bird_seen:
                return State.HOVERING, "Bird not detected"

        # Hovering state
        case State.HOVERING:
            if should_dock:
                return State.DOCKING_INIT, "Should dock"
            if safe and bird_seen:
                return State.TRACKING, "Bird detected"

        # Docking initialization state
        # Hold here until Safety permits the approach (it blocks it for a moving cart or people nearby).
        case State.DOCKING_INIT:
            if safety.get("approach_permitted") is True:
                return State.DOCKING_APPROACH, "Approach permitted"

        # Docking approach state
        # Abort on a docking failure. Only Docking's landed_on_pad confirms landing
        case State.DOCKING_APPROACH:
            if docking.get("phase") == "abort":
                return State.ABORT, "Docking failed"
            if safety.get("approach_permitted") is not True:
                return State.ABORT, "Approach not permitted"
            if docking.get("phase") == "descend" and safety.get("descent_permitted") is not True:
                return State.ABORT, "Descent not permitted"
            if docking.get("landed_on_pad") is True:
                return State.DOCKED, "Landed on pad"

        # Docked state
        case State.DOCKED:
            if percent > 85:
                return State.IDLE, "Battery charged"

        # Abort state
        # When Safety permits holding, retry docking, otherwise stay in ABORT
        # TODO: go to EMERGENCY_LAND when not recoverable (e.g. too many failed docking attempts)
        case State.ABORT:
            if safety.get("hold_permitted") is True:
                return State.DOCKING_INIT, "Retrying docking"

        # Emergency land state
        # Terminal until the team decides how to reset it
        case State.EMERGENCY_LAND:
            pass

    return state, None
