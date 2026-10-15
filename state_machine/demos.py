# Scripted demo scenarios for run_loop.py.
#
# Each scenario is a list of tuples, where each tuple contains:
# - The time step in milliseconds.
# - The changes to apply to the world at that time (only the listed fields change).
#
# Times must be multiples of the tick length (100 ms).

# Safety's permissions when a moving cart or people nearby block everything except hold
HOLD_ONLY = {"launch": False, "tracking": False, "approach": False, "descent": False, "hold": True}

BIRD_SEEN = {"detected": True, "type": "hawk", "distance_m": 30.0}
BIRD_GONE = {"detected": False, "type": None, "distance_m": None}


# Full cycle: launch for a bird, lose it, return on low battery, wait for the cart, land, recharge.
# Run for 10000 ms.
# IDLE -> HOVERING -> TRACKING -> HOVERING -> DOCKING_INIT -> DOCKING_APPROACH -> DOCKED -> IDLE
DEMO_SCENARIO = [
    (1000, {"bird": {"detected": True, "type": "hawk", "distance_m": 30.0}}),
    (4000, {"bird": {"detected": False, "type": None, "distance_m": None}}),
    # Low battery and a moving cart: Safety blocks everything except hold
    (5000, {"battery": {"percent": 18}, "docking": {"should_dock": True, "reason": "low_battery"},
            "safety": {"permissions": {"launch": False, "tracking": False, "approach": False, "descent": False, "hold": True},
                       "battery_low": True, "battery_recovered": False, "reasons": ["low_battery", "cart_moving"]}}),
    # The cart stops, so approach and descent are permitted; low battery still blocks launch and tracking
    (6000, {"safety": {"permissions": {"launch": False, "tracking": False, "approach": True, "descent": True, "hold": True},
                       "reasons": ["low_battery"]}}),
    (6100, {"docking": {"phase": "approach"}}),
    (7000, {"docking": {"phase": "align"}}),
    (7500, {"docking": {"phase": "descend"}}),
    (9000, {"docking": {"phase": "complete", "landed_on_pad": True, "should_dock": False, "reason": None}}),
    (9500, {"battery": {"percent": 90},
            "safety": {"permissions": {"launch": True, "tracking": True, "approach": True, "descent": True, "hold": True},
                       "battery_low": False, "battery_recovered": True, "reasons": []}}),
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


# Safety raises an emergency while tracking: the drone lands in place and stays in EMERGENCY_LAND.
# Run for 9000 ms.
# IDLE -> HOVERING -> TRACKING -> EMERGENCY_LAND
EMERGENCY_SCENARIO = [
    (500, {"bird": BIRD_SEEN}),
    (3000, {"battery": {"percent": 8},
            "safety": {"emergency": True, "battery_critical": True, "reasons": ["critical_battery"]}}),
]


# The dock stays blocked, so the drone holds in DOCKING_INIT and never starts the approach.
# Run for 5500 ms.
# IDLE -> HOVERING -> TRACKING -> DOCKING_INIT
BLOCKED_DOCK_SCENARIO = [
    (500, {"bird": BIRD_SEEN}),
    (3000, {"bird": BIRD_GONE, "docking": {"should_dock": True, "reason": "no_bird"},
            "safety": {"permissions": HOLD_ONLY, "reasons": ["cart_moving"]}}),
]


# Demo name -> (scenario, how long to run it in ms).
# Used by: python3 -m state_machine.run_loop <name>
DEMOS = {
    "full_cycle": (DEMO_SCENARIO, 10000),
    "docking_retry": (DOCKING_RETRY_SCENARIO, 8000),
    "emergency": (EMERGENCY_SCENARIO, 9000),
    "blocked_dock": (BLOCKED_DOCK_SCENARIO, 5500),
}
