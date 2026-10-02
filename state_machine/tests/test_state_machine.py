import pytest

from state_machine.run_loop import run_world
from state_machine.state_machine import step, State

AIRBORNE_STATES = [State.TRACKING, State.HOVERING, State.DOCKING_INIT, State.DOCKING_APPROACH, State.ABORT]

def safety_with(**changes):
    # All-clear safety flags with some changed, e.g. safety_with(cart_moving=True)
    # approach_permitted / descent_permitted / hold_permitted are Safety's permissions (INTEGRATION_README.md section 6)
    safety = {
        "people_nearby": False,
        "cart_moving": False,
        "weather": "clear",
        "camera_ok": True,
        "comm_ok": True,
        "approach_permitted": True,
        "descent_permitted": True,
        "hold_permitted": True,
    }
    safety.update(changes)
    return safety

def docking_with(**changes):
    # Default docking flags with some changed, e.g. docking_with(should_dock=True, phase="descend")
    # phase is one of: idle, approach, search, align, descend, complete, abort
    docking = {
        "should_dock": False,
        "reason": None,
        "phase": "idle",
        "landed_on_pad": False,
    }
    docking.update(changes)
    return docking

def make_observation(bird = None, battery = None, safety = None, docking = None):
    # Makes observations in the team's JSON format for testing purposes
    return {
        "bird": bird or {"detected": False},
        "battery": battery or {"percent": 100, "low": False},
        "safety": safety or safety_with(),
        "docking": docking or docking_with(),
    }

def test_idle_to_hovering():
    # A launch goes through HOVERING before TRACKING
    observation = make_observation(bird={"detected": True})
    new_state, reason = step(State.IDLE, observation)
    assert new_state == State.HOVERING
    assert reason == "Bird detected"

def test_tracking_to_hovering():
    observation = make_observation(bird={"detected": False})
    new_state, reason = step(State.TRACKING, observation)
    assert new_state == State.HOVERING
    assert reason == "Bird not detected"

def test_idle_to_detected_bird():
    observation = make_observation(bird={"type": "sparrow", "detected": True, "distance_m": 5})
    assert step(State.IDLE, observation) == (State.HOVERING, "Bird detected")

def test_lost_bird_to_hovering():
    observation = make_observation(bird={"detected": False})
    assert step(State.TRACKING, observation) == (State.HOVERING, "Bird not detected")

def test_missing_bird_data_to_hovering():
    # Only the state is checked: the reason depends on whether bird-lost or unsafe is checked first
    assert step(State.TRACKING, {})[0] == State.HOVERING

def test_idle_does_not_launch_when_unsafe():
    observation = make_observation(bird={"detected": True}, safety=safety_with(cart_moving=True))
    assert step(State.IDLE, observation)[0] == State.IDLE

def test_idle_with_should_dock_stays_idle():
    # IDLE is already on the dock, so a grounded drone ignores return requests
    observation = make_observation(docking=docking_with(should_dock=True, reason="no_bird"))
    assert step(State.IDLE, observation)[0] == State.IDLE

def test_tracking_should_dock_to_docking_init():
    observation = make_observation(bird={"detected": True}, docking=docking_with(should_dock=True, reason="low_battery"))
    assert step(State.TRACKING, observation)[0] == State.DOCKING_INIT

def test_hovering_should_dock_to_docking_init():
    observation = make_observation(docking=docking_with(should_dock=True))
    assert step(State.HOVERING, observation)[0] == State.DOCKING_INIT

def test_hovering_to_tracking():
    observation = make_observation(bird={"detected": True})
    assert step(State.HOVERING, observation) == (State.TRACKING, "Bird detected")

def test_docked_to_idle_when_battery_recovered():
    recovered = make_observation(battery={"percent": 100})
    assert step(State.DOCKED, recovered)[0] == State.IDLE

    still_low = make_observation(battery={"percent": 18})
    assert step(State.DOCKED, still_low)[0] == State.DOCKED

def test_docking_init_waits_for_approach_permission():
    # Safety blocks the approach (e.g. cart moving), so the drone holds in DOCKING_INIT
    blocked = make_observation(docking=docking_with(should_dock=True),
                               safety=safety_with(cart_moving=True, approach_permitted=False))
    assert step(State.DOCKING_INIT, blocked)[0] == State.DOCKING_INIT

    permitted = make_observation(docking=docking_with(should_dock=True))
    assert step(State.DOCKING_INIT, permitted)[0] == State.DOCKING_APPROACH

def test_approach_waits_for_landed_on_pad():
    # Docking is still working in these phases, so the state machine waits
    for phase in ["idle", "approach", "search", "align", "descend"]:
        observation = make_observation(docking=docking_with(should_dock=True, phase=phase))
        assert step(State.DOCKING_APPROACH, observation)[0] == State.DOCKING_APPROACH, phase

    landed = make_observation(docking=docking_with(phase="complete", landed_on_pad=True))
    assert step(State.DOCKING_APPROACH, landed)[0] == State.DOCKED

def test_approach_aborts_when_docking_fails():
    failed = make_observation(docking=docking_with(should_dock=True, phase="abort"))
    assert step(State.DOCKING_APPROACH, failed)[0] == State.ABORT

def test_approach_aborts_when_permission_lost():
    no_approach = make_observation(docking=docking_with(should_dock=True, phase="align"),
                                   safety=safety_with(people_nearby=True, approach_permitted=False))
    assert step(State.DOCKING_APPROACH, no_approach)[0] == State.ABORT

    # Descent permission only matters once docking is descending
    no_descent = make_observation(docking=docking_with(should_dock=True, phase="descend"),
                                  safety=safety_with(descent_permitted=False))
    assert step(State.DOCKING_APPROACH, no_descent)[0] == State.ABORT

    aligning = make_observation(docking=docking_with(should_dock=True, phase="align"),
                                safety=safety_with(descent_permitted=False))
    assert step(State.DOCKING_APPROACH, aligning)[0] == State.DOCKING_APPROACH

def test_unsafe_goes_to_hovering_not_emergency_land():
    stormy = make_observation(bird={"detected": True}, safety=safety_with(weather="storm"))
    assert step(State.TRACKING, stormy)[0] == State.HOVERING

def test_abort_retries_docking():
    # ABORT happens because docking went wrong, so the hazard may still be there;
    # recovering means trying docking again, not landing in place
    person_at_dock = make_observation(docking=docking_with(should_dock=True),
                                      safety=safety_with(people_nearby=True, approach_permitted=False))
    assert step(State.ABORT, person_at_dock)[0] == State.DOCKING_INIT

def test_abort_stays_when_hold_not_permitted():
    no_hold = make_observation(docking=docking_with(should_dock=True), safety=safety_with(hold_permitted=False))
    assert step(State.ABORT, no_hold)[0] == State.ABORT

def test_emergency_land_is_final():
    assert step(State.EMERGENCY_LAND, make_observation())[0] == State.EMERGENCY_LAND

def test_demo_runs_full_cycle():
    # Nominal mission trace from INTEGRATION_README.md section 11
    states = [new for _, _, new, _ in run_world(10000)]
    assert states == [State.HOVERING, State.TRACKING, State.HOVERING, State.DOCKING_INIT,
                      State.DOCKING_APPROACH, State.DOCKED, State.IDLE]