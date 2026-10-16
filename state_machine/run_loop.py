
import argparse
import copy
import time
import dataclasses

from state_machine.demos import DEMO_SCENARIO, DEMOS
from safety_layer.safety_policy import assess
from state_machine.state_machine import State, step
from universal_log.Universal_log import UniversalLog
from motion_engine.contracts import Command, MotionCommandType, Pose, SimulationClock
from motion_engine.motion_stubs import MotionStub
from motion_engine.safety_adapter import check_for_motion


TICK_HZ = 10
TICK_MS = 1000 // TICK_HZ  # 100 ms per tick

VALIDITY_NS = 200_000_000  # a Motion command lasts 0.2 s unless it is renewed
PAD = Pose(0, 0, 0, 0)     # the fixed landing pad, on the ground at the origin

# Motion runs these once; they are never renewed and have no expiry
ONE_SHOT_KINDS = {MotionCommandType.DISARM, MotionCommandType.EMERGENCY_LAND}


# How every drone should be initialized: default values - 
def init_world() -> dict:
    return {
        "bird": {"detected": False, "type": None, "distance_m": None},
        "battery": {"percent": 100, "valid": True},
        "environment": {
            "people_nearby": False,
            "cart_moving": False,
            "weather": "clear",
            "camera_ok": True,
            "comm_ok": True,
            "valid": True
        },
        "dock": {
            "alignment_valid": True,
            "valid": True
        },
        "docking": {"phase": "idle", "landed_on_pad": False, "should_dock": False, "reason": None},
    }


# Arm and take off. Called once, when the mission goes IDLE -> HOVERING.
# Motion rejects a reused command id, so each launch gets its own number.
def launch_drone(motion, clock, state, reason, launch_number, assessment):
    now = clock.timestamp_ns
    commands = [
        Command(f"arm-{launch_number}", MotionCommandType.ARM, state.value, now, None, "state_machine", reason),
        Command(f"takeoff-{launch_number}", MotionCommandType.TAKEOFF, state.value, now, None, "state_machine", reason,
                target=Pose(0, 0, 5.0, 0)),
    ]
    acks = []
    for command in commands:
        command, decision = check_for_motion(command, assessment, now)
        ack = motion.submit(command, now)
        if not ack.accepted:
            raise RuntimeError(f"Motion rejected {command.command_id}: {ack.reason}")
        acks.append(ack)
    return acks


# True while the takeoff climb is still going. Sending any other command during
# the climb replaces the takeoff and leaves the drone stuck near the ground.
def still_climbing(vehicle) -> bool:
    return vehicle.active_kind == MotionCommandType.TAKEOFF and not vehicle.arrived


# Decide which Motion command the mission state wants on this tick.
# vehicle is Motion's feedback from the previous tick (pose, armed, airborne, grounded, ...).
# Return (kind, target) to send or renew a command, or None to send nothing.
#   kind:   a MotionCommandType, e.g. MotionCommandType.HOVER
#   target: a Pose for commands that fly somewhere (e.g. PAD), otherwise None
def wanted_command(state, vehicle):
    match state:
        case State.HOVERING:
            if still_climbing(vehicle):
                return None
            return MotionCommandType.HOVER, None
        case State.DOCKING_INIT:
            return MotionCommandType.HOVER, None
        case State.ABORT:
            return MotionCommandType.STOP, None
        case State.DOCKING_APPROACH:
            return MotionCommandType.DESCEND_TO_DOCK, PAD
        case State.DOCKED:
            if vehicle.armed and vehicle.grounded:
                return MotionCommandType.DISARM, None
        case State.EMERGENCY_LAND:
            return MotionCommandType.EMERGENCY_LAND, None
        case State.IDLE:
            return None
        case State.TRACKING:
            return None
            
    return None


# Send the wanted command to Motion, or renew it if it is the same one as last tick.
# active remembers the last command: {"number": int, "kind": ..., "target": ...}.
# Returns Motion's ack, or None when nothing was sent.
def send_command(motion, clock, active, state, reason, wanted, assessment):
    if wanted is None:
        # Forget the last command: Motion rejects an id that is reused after it expired
        active["kind"], active["target"] = None, None
        return None

    kind, target = wanted
    same_as_last = kind == active["kind"] and target == active["target"]
    if same_as_last and kind in ONE_SHOT_KINDS:
        return None  # already sent once
    if not same_as_last:
        active["number"] += 1  # a different command gets a new id

    now = clock.timestamp_ns
    expires = None if kind in ONE_SHOT_KINDS else now + VALIDITY_NS
    command = Command(f"sm-{active['number']}", kind, state.value, now, expires,
                      "state_machine", reason or "renew", target=target)
    command, decision = check_for_motion(command, assessment, now)
    ack = motion.submit(command, now)
    if ack.accepted:
        active["kind"], active["target"] = kind, target
    else:
        # Forget it, so the next tick tries again with a new id
        active["kind"], active["target"] = None, None
        print(f"Motion rejected {command.command_id} ({kind.value}): {ack.reason}")
    return ack


def run_world(duration_ms: int, real_time: bool = False, log_transitions: bool = False,
              scenario: list = DEMO_SCENARIO, viewPosition: bool = False):
    world = init_world()
    currState = State.IDLE
    clock = SimulationClock()
    motion = MotionStub(clock=clock)
    launches = 0
    active = {"number": 0, "kind": None, "target": None}  # the last command sent to Motion
    vehicle = motion.feedback(clock.timestamp_ns)          # Motion's feedback from the previous tick
    transitions = []
    commands = []            # every new command sent to Motion: (time_ms, kind, accepted, reason)
    last_command_id = None   # so a command renewed every tick is only recorded once
    for tick in range(duration_ms // TICK_MS):
        current_time_ms = tick * TICK_MS

        # 1. Update what changes in the world at the specified time
        for event_time_ms, observation in scenario:
            if current_time_ms == event_time_ms:
                for section, values in observation.items():
                    world[section].update(values)

        # 2. Run the state machine each tick using a snapshot of current situation
        snapshot = copy.deepcopy(world)
        snapshot["timestamp_ns"] = clock.timestamp_ns
        now_ns = clock.timestamp_ns
        for section in ["battery", "dock", "environment"]:
            if section in snapshot:
                snapshot[section]["timestamp_ns"] = now_ns

        snapshot["vehicle"] = vehicle.to_dict()
        snapshot["context"] = {
            "flight_active": vehicle.airborne or vehicle.armed
        }
        assessment = assess(snapshot, now_ns)
        snapshot["safety"] = dataclasses.asdict(assessment)
        newState, reason = step(currState, snapshot)

        # When the drone launches (IDLE -> HOVERING), arm and take off once
        if currState == State.IDLE and newState == State.HOVERING:
            launches += 1
            for ack in launch_drone(motion, clock, newState, reason, launches, assessment):
                commands.append((current_time_ms, ack.kind, ack.accepted, ack.reason))
            vehicle = motion.feedback(clock.timestamp_ns)  # so the takeoff shows as the active command

        # Send (or renew) the command this state wants, before Motion moves this tick
        ack = send_command(motion, clock, active, newState, reason, wanted_command(newState, vehicle), assessment)
        if ack is not None and ack.command_id != last_command_id:
            commands.append((current_time_ms, ack.kind, ack.accepted, ack.reason))
            last_command_id = ack.command_id

        # Every tick: move the simulated drone, then read where it is
        motion.step(TICK_MS / 1000, now_ns=clock.timestamp_ns)
        vehicle = motion.feedback(clock.timestamp_ns)
        clock.advance(TICK_MS/1000)
        if (viewPosition):
            print(current_time_ms, "z =", vehicle.pose.z, "airborne =", vehicle.airborne)

        # 3. Only log real transitions
        if newState != currState:
            if log_transitions:
                UniversalLog({
                                "State": newState.value,
                                "Details": {
                                    "module": "state_machine",
                                    "timestamp": current_time_ms,
                                    "reason": reason,
                                    "from": currState.value,
                                    "to": newState.value
                                }
                            }, True)
            transitions.append((current_time_ms, currState, newState, reason))
            currState = newState
        if real_time:
            time.sleep(TICK_MS / 1000)  # Sleep for the duration of one tick in seconds

    return {
        "transitions": transitions,  # (time_ms, from_state, to_state, reason) for each state change
        "commands": commands,        # (time_ms, kind, accepted, reason) for each new command sent to Motion
        "vehicle": vehicle,          # Motion's feedback after the last tick: pose, armed, airborne, grounded, ...
    }

if __name__ == "__main__":
    # Pick a demo by name: python3 -m state_machine.run_loop emergency
    parser = argparse.ArgumentParser(description="Run a scripted demo through the state machine and Motion.")
    parser.add_argument("demo", nargs="?", default="full_cycle", choices=sorted(DEMOS),
                        help="which demo to run (default: full_cycle)")
    args = parser.parse_args()

    scenario, duration_ms = DEMOS[args.demo]
    result = run_world(duration_ms, True, True, scenario, False)
    for currentTimeMs, currState, newState, reason in result["transitions"]:
        print(f"({currentTimeMs}ms) {currState.value} -> {newState.value}: Reason: {reason}")
