# Scripted demo scenarios for run_loop.py.
#
# Each scenario is a list of tuples, where each tuple contains:
# - The time step in milliseconds.
# - The changes to apply to the world at that time (only the listed fields change).
#
# Scenarios script facts about the world (battery, environment, dock), not Safety's answers:
# Safety's assess() works out the permissions from these facts every tick.
#
# Times must be multiples of the tick length (100 ms).

BIRD_SEEN = {"detected": True, "type": "hawk", "distance_m": 30.0}
BIRD_GONE = {"detected": False, "type": None, "distance_m": None}


# Full cycle: launch for a bird, lose it, return on low battery, wait for the cart, land, recharge.
# Run for 10000 ms.
# IDLE -> HOVERING -> TRACKING -> HOVERING -> DOCKING_INIT -> DOCKING_APPROACH -> DOCKED -> IDLE
DEMO_SCENARIO = [
    (1000, {"bird": {"detected": True, "type": "hawk", "distance_m": 30.0}}),
    (4000, {"bird": {"detected": False, "type": None, "distance_m": None}}),
    # Low battery and the cart starts moving: Safety allows only hold
    (5000, {"battery": {"percent": 18}, "docking": {"should_dock": True, "reason": "low_battery"},
            "environment": {"cart_moving": True}}),
    # The cart stops: Safety allows approach and descent again (low battery still blocks launch and tracking)
    (6000, {"environment": {"cart_moving": False}}),
    (6100, {"docking": {"phase": "approach"}}),
    (7000, {"docking": {"phase": "align"}}),
    (7500, {"docking": {"phase": "descend"}}),
    (9000, {"docking": {"phase": "complete", "landed_on_pad": True, "should_dock": False, "reason": None}}),
    (9500, {"battery": {"percent": 90}}),
]


# Docking fails on the first attempt, the mission aborts, then it retries and lands.
# Run for 8000 ms.
# IDLE -> HOVERING -> TRACKING -> DOCKING_INIT -> DOCKING_APPROACH -> ABORT
#      -> DOCKING_INIT -> DOCKING_APPROACH -> DOCKED -> IDLE
DOCKING_RETRY_SCENARIO = [
    (500, {"bird": BIRD_SEEN}),
    # The bird leaves and Docking asks to return
    (3000, {"bird": BIRD_GONE, "docking": {"should_dock": True, "reason": "no_bird"}}),
    # Docking gives up on this attempt, then resets for the next one
    (4000, {"docking": {"phase": "abort"}}),
    (4100, {"docking": {"phase": "idle"}}),
    (6500, {"docking": {"phase": "complete", "landed_on_pad": True, "should_dock": False, "reason": None}}),
]


# The battery drops to 8% while tracking: Safety raises an emergency (critical battery),
# so the drone lands in place, disarms, and stays in EMERGENCY_LAND.
# Run for 9000 ms.
# IDLE -> HOVERING -> TRACKING -> EMERGENCY_LAND
EMERGENCY_SCENARIO = [
    (500, {"bird": BIRD_SEEN}),
    (3000, {"battery": {"percent": 8}}),
]


# The cart keeps moving, so Safety never allows the approach: the drone holds in DOCKING_INIT.
# Run for 5500 ms.
# IDLE -> HOVERING -> TRACKING -> DOCKING_INIT
BLOCKED_DOCK_SCENARIO = [
    (500, {"bird": BIRD_SEEN}),
    (3000, {"bird": BIRD_GONE, "docking": {"should_dock": True, "reason": "no_bird"},
            "environment": {"cart_moving": True}}),
]


# The drone reaches the dock before it is lined up with the pad. Safety does not allow descent,
# so it replaces the descent command with a hover until the alignment is valid at 5000 ms.
# Run for 9000 ms.
# IDLE -> HOVERING -> TRACKING -> DOCKING_INIT -> DOCKING_APPROACH -> DOCKED -> IDLE
NOT_ALIGNED_SCENARIO = [
    (500, {"bird": BIRD_SEEN}),
    (3000, {"bird": BIRD_GONE, "docking": {"should_dock": True, "reason": "no_bird"},
            "dock": {"alignment_valid": False}}),
    (5000, {"dock": {"alignment_valid": True}}),
    (8000, {"docking": {"phase": "complete", "landed_on_pad": True, "should_dock": False, "reason": None}}),
]


# The cart starts moving while the drone is descending. Safety withdraws the approach,
# the mission aborts and waits in DOCKING_INIT until the cart stops, then lands.
# Run for 10000 ms.
# IDLE -> HOVERING -> TRACKING -> DOCKING_INIT -> DOCKING_APPROACH -> ABORT
#      -> DOCKING_INIT -> DOCKING_APPROACH -> DOCKED -> IDLE
CART_DURING_DESCENT_SCENARIO = [
    (500, {"bird": BIRD_SEEN}),
    (3000, {"bird": BIRD_GONE, "docking": {"should_dock": True, "reason": "no_bird"}}),
    (4000, {"environment": {"cart_moving": True}}),
    (6000, {"environment": {"cart_moving": False}}),
    (9000, {"docking": {"phase": "complete", "landed_on_pad": True, "should_dock": False, "reason": None}}),
]


# Communication is lost while tracking: Safety raises an emergency (comm loss),
# so the drone lands in place, disarms, and stays in EMERGENCY_LAND.
# Run for 9000 ms.
# IDLE -> HOVERING -> TRACKING -> EMERGENCY_LAND
COMM_LOSS_SCENARIO = [
    (500, {"bird": BIRD_SEEN}),
    (3000, {"environment": {"comm_ok": False}}),
]


# Demo name -> (scenario, how long to run it in ms).
# Used by: python3 -m state_machine.run_loop <name>
DEMOS = {
    "full_cycle": (DEMO_SCENARIO, 10000),
    "docking_retry": (DOCKING_RETRY_SCENARIO, 8000),
    "emergency": (EMERGENCY_SCENARIO, 9000),
    "blocked_dock": (BLOCKED_DOCK_SCENARIO, 5500),
    "not_aligned": (NOT_ALIGNED_SCENARIO, 9000),
    "cart_during_descent": (CART_DURING_DESCENT_SCENARIO, 10000),
    "comm_loss": (COMM_LOSS_SCENARIO, 9000),
}
