# State Machine — Phase 0

[Phase 0 scope: Start Here](../START_HERE.md)

## Purpose

Decide the drone's current mission state each tick of the synthetic simulation loop. The state machine reads the shared observation produced by CV, Safety, and Docking, selects the next state, and records why. Motion acts on the chosen state; the state machine never moves the vehicle or detects anything itself.

Phase 0 is purely synthetic: all inputs are generated values, not sensor or simulator data. The state machine is written so that Phase 1 can supply real observations without changing its logic.

## States

| State | Where | Meaning | Motion command sent by `run_loop.py` |
|---|---|---|---|
| `IDLE` | On the dock | On the dock or grounded, waiting for a reason to launch | None |
| `TRACKING` | Air | Airborne and following a detected bird | None yet (needs a tracking target; Navigation has no code) |
| `HOVERING` | Launching from the dock, or air | Launching (arming and climbing), or airborne and holding position (bird lost, temporarily unsafe, or waiting to dock) | `ARM` + `TAKEOFF` once when coming from `IDLE`; `HOVER` once the climb has finished |
| `DOCKING_INIT` | Air | Docking requested; checking that the dock can be approached | `HOVER` while waiting for approach permission |
| `DOCKING_APPROACH` | Air → landing on the dock | Moving toward and descending onto the dock | `DESCEND_TO_DOCK` to the pad (a shortcut until Docking proposes the target) |
| `DOCKED` | On the dock | Landed on the dock | `DISARM`, once the drone is on the ground |
| `ABORT` | Air | Current action cancelled; deciding whether to recover or land | `STOP` (hold in place) |
| `EMERGENCY_LAND` | Air → landing where it is | Synthetic only. Land immediately at the current position | `EMERGENCY_LAND`, once |

These names are part of the Phase 0 → Phase 1 interface contract and must not change without team agreement.

- `IDLE` and `DOCKED` are both on the dock. `DOCKED` means just landed with the battery not yet recovered; it becomes `IDLE` once the battery has recovered.
- There is no separate takeoff state: `HOVERING` includes the launch ([integration contract](../INTEGRATION_README.md) section 2). A launch goes `IDLE → HOVERING → TRACKING`. Holding `TRACKING` back until the climb finishes needs a launch-progress input that the team has not agreed yet.
- In Phase 0, "the dock" is a stationary pad in simulation. The golf-cart dock is the long-term product (see [Start Here](../START_HERE.md)).
- The Motion command for each state is chosen by `wanted_command()` in `run_loop.py`. The mapping is a proposal and needs agreement with the Motion team. Command names are Motion's `MotionCommandType` ([`motion_engine/contracts.py`](../motion_engine/contracts.py)). The state machine only chooses the state; the loop issues the command.

## Inputs and outputs

- Input: the current state and one observation per tick (see the observation format below).
- Output: the next state and a transition reason, written to the observation's `state` field and to the log.
- The state machine reads Docking's `should_dock`, `reason`, `phase` and `landed_on_pad`; it does not re-evaluate docking triggers itself. Likewise, it reads the Safety layer's decisions (`permissions`, `emergency`, `abort` and `battery_recovered`) rather than re-deriving safety rules, so it never checks whether the dock is clear itself.
- Those Safety decisions are worked out every tick by Safety's `assess()`, which `run_loop.py` calls before `step()` (see "Safety integration" below).

Proposed interface:

```python
next_state, reason = step(current_state, observation)
```

`step()` has no side effects, which keeps it deterministic and easy to unit test.

### Observation format (draft, to be agreed with all modules)

What `step()` receives on one tick of the `full_cycle` demo (5000 ms: low battery, cart moving):

```json
{
  "timestamp_ns": 5000000000,
  "bird":        { "detected": false, "type": null, "distance_m": null },
  "battery":     { "percent": 18, "valid": true, "timestamp_ns": 5000000000 },
  "environment": { "people_nearby": false, "cart_moving": true, "weather": "clear",
                   "camera_ok": true, "comm_ok": true, "valid": true, "timestamp_ns": 5000000000 },
  "dock":        { "alignment_valid": true, "valid": true, "timestamp_ns": 5000000000 },
  "vehicle":     { "armed": true, "airborne": true, "grounded": false, "pose": { "x": 0.0, "y": 0.0, "z": 5.0, "yaw_deg": 0.0 },
                   "valid": true, "timestamp_ns": 4900000000, "...": "the rest of Motion's VehicleFeedback" },
  "context":     { "flight_active": true },
  "safety":      { "permissions": { "launch": false, "tracking": false, "approach": false, "descent": false, "hold": true },
                   "emergency": false, "abort": false, "battery_low": true, "battery_critical": false,
                   "battery_recovered": false, "reasons": ["low_battery", "cart_moving"], "timestamp_ns": 5000000000 },
  "docking":     { "should_dock": true, "reason": "low_battery", "phase": "idle", "landed_on_pad": false }
}
```

| Section | Comes from |
|---|---|
| `bird`, `battery`, `environment`, `dock`, `docking` | The demo scenario (`demos.py`). `bird` will come from CV and `docking` from Docking once they are connected. |
| `vehicle` | Motion's feedback from the previous tick (`VehicleFeedback.to_dict()`) |
| `context` | `run_loop.py`: `flight_active` is true while the drone is armed or airborne |
| `safety` | Safety's `assess()`, worked out from the sections above |

`step()` reads `bird`, `safety` and `docking`. The other sections are what Safety needs to decide.

## Docking triggers

Docking may be requested for any of the following. Docking computes `should_dock`; the state machine decides what that means in the current state.

1. Low battery
2. No bird detected
3. People approaching
4. Cart moving
5. Weather hazard
6. Camera failure
7. Communication loss

## Transitions (draft)

Rules are checked in priority order and the first match wins:

1. **Global overrides.** In any airborne state, Safety's `emergency` goes to `EMERGENCY_LAND`, then Safety's `abort` goes to `ABORT` (except from `ABORT` itself).
2. **Per-state rules.** From the table below.
3. **Default.** No match means the state is unchanged.

| From | Condition | To |
|---|---|---|
| `IDLE` | `should_dock` | Ignored; stays `IDLE` (a grounded drone ignores return requests) |
| `IDLE` | Bird detected and `launch` permitted | `HOVERING` (start the launch) |
| `TRACKING` | `should_dock` | `DOCKING_INIT` |
| `TRACKING` | `tracking` not permitted | `HOVERING` |
| `TRACKING` | Bird lost | `HOVERING` |
| `HOVERING` | `should_dock` or hover timeout | `DOCKING_INIT` |
| `HOVERING` | Bird detected and `tracking` permitted | `TRACKING` |
| `DOCKING_INIT` | Safety permits the approach (`approach`) | `DOCKING_APPROACH` |
| `DOCKING_INIT` | Approach not permitted | Stay and hold |
| `DOCKING_APPROACH` | Docking phase `abort`, approach permission lost, or descent permission lost while descending | `ABORT` |
| `DOCKING_APPROACH` | Docking confirms `landed_on_pad` | `DOCKED` |
| `DOCKED` | Safety reports `battery_recovered` | `IDLE` |
| `ABORT` | Safety permits holding (`hold`) | `DOCKING_INIT` (retry docking) |
| `ABORT` | Holding not permitted | Stay in `ABORT` |
| `ABORT` | Not recoverable | `EMERGENCY_LAND` |
| Any airborne state | Safety `emergency` (e.g. critical battery) | `EMERGENCY_LAND` |
| Any airborne state except `ABORT` | Safety `abort` (e.g. operator abort) | `ABORT` |

The cart-motion rule in the [main README](../README.md) applies: the drone never lands on a moving cart. While the cart is moving, docking waits in a safe state.

Docking rules follow the [integration contract](../INTEGRATION_README.md) (sections 6–8):

- Safety decides whether the approach and descent are permitted. People nearby or a moving cart block both; the drone holds in `DOCKING_INIT` until the approach is permitted.
- Docking's local `phase` (`idle`, `approach`, `search`, `align`, `descend`, `complete`, `abort`; see [`docking/states/docking_state.py`](../docking/states/docking_state.py)) only runs while the mission is in `DOCKING_APPROACH`.
- Docking reports `landed_on_pad` once touchdown is confirmed, and phase `abort` when the attempt fails.

The `safety` field names come from Safety's `SafetyAssessment` (PR #61). The Docking field names `phase` and `landed_on_pad` are proposed; confirm them with the Docking team.

### Open questions

- Which conditions lead to docking, which to abort, and which to emergency landing (for example, low vs. critical battery, or communication loss during approach)?
- Does losing the bird start docking immediately or after a hover timeout?
- What is the priority order when several triggers are active in the same tick?
- How does the system leave `EMERGENCY_LAND`: terminal, or manual reset to `IDLE`?
- Which module owns the overall "safe" decision? Proposed: Safety provides it and the state machine consumes it.

## Logging

Use the shared Phase 0 logging format:

```
[timestamp] [module] [event] [state] [synthetic_truth] [decision]
```

The state machine logs the current state every tick and logs every transition with the previous state, the new state, and the reason:

```
[12:03:22.120] STATE: TRACKING
[12:03:25.480] STATE: transition TRACKING -> DOCKING_INIT (reason=low_battery)
```

## First tasks

1. Agree on the states, transition table, and open questions with Docking, Safety, and Motion.
2. Agree on the shared observation format and thresholds (low/critical battery, landing tolerance, hover timeout).
3. Implement the `State` enum and `step()`.
4. Emit log lines using the shared logger.
5. Write unit tests: one per transition, one per docking trigger, and cases with several triggers at once.
6. Integrate into the simulation loop between Docking and Motion.
7. Verify that changing values during a running simulation produces the expected transitions.
8. Document the state machine's update rate for the Phase 1 interface contract.

## Acceptance evidence

Every transition in the agreed table is covered by a passing test. Each docking trigger, injected during a running synthetic simulation, produces the expected state change with a logged reason. Invalid or missing observation fields produce a defined state rather than an unhandled error.

## Phase 1 notes

Phase 1 must implement the same states and respect them in motion control. Real observations replace synthetic ones through the same observation format; the transition logic should not need to change.

Simulation loop:
Pretend 3D coordinates
CV: Feed birds into camera (Bird? Safetycheck & Dockcheck : Do nothing) Predefined states for images (Kind of bird, distance away) - Elias C
Dock (battery power, people show up, cart is ready to move, no birds, weather conditions, camera failure, lose communication)? Initiate Docking : Do nothing) - Elias N
Safety layer (Safetycheck? Move : Don’t Move/Possible dock check) - Jermaine
Motion ( Move to new X,Y, Z; Leave comments in code for any place a real movement or orientation command might need to be) - Connor
State Machine - Mykolas
Universal logging - Will
Part of Phase 0 Deliverable is what is needed for Phase 1.


Be able to, in a running simulation, test each of these values changing.


## Safety integration

`run_loop.py` asks Safety what is allowed every tick, before `step()`:

1. It builds the snapshot: the scenario's `battery`, `environment` and `dock` facts, each stamped with the current time; Motion's feedback as `vehicle`; and `context` with `flight_active`.
2. It calls Safety's `assess(snapshot, now_ns)` ([`safety_layer/safety_policy.py`](../safety_layer/safety_policy.py)) and puts the answer in `snapshot["safety"]`, where `step()` reads it.

Safety fails closed: a missing section, or one older than 0.5 s, counts as not permitted. Its emergency rules (critical battery, lost comms, bad weather, stale data) only apply while `flight_active` is true.

Every command then passes through `check_for_motion()` ([`motion_engine/safety_adapter.py`](../motion_engine/safety_adapter.py)) before it reaches Motion. If Safety does not permit it, Safety sends a replacement instead: `HOVER`, `LAND` if holding is not permitted either, or `EMERGENCY_LAND` during an emergency. A replacement's command id ends in `-safety`.

## Motion integration

`run_loop.py` drives Motion's simulated drone (`MotionStub`) from the mission state. `step()` still only decides the state; it never sends a command.

Each tick, after `step()`:

1. On `IDLE → HOVERING`, `launch_drone()` sends `ARM` and `TAKEOFF` once.
2. `wanted_command(state, vehicle)` picks the command for the current state (the last column of the States table), using Motion's feedback from the previous tick.
3. `send_command()` sends it, after Safety's command check:
   - `HOVER`, `STOP` and `DESCEND_TO_DOCK` are valid for 0.2 s and are renewed every tick with the same command id. A different command gets a new id.
   - `DISARM` and `EMERGENCY_LAND` are sent once.
4. `motion.step()` moves the drone by one tick, and `motion.feedback()` reads its new status.

Nothing is sent while the takeoff is still climbing, because a new command would replace the takeoff.

Not connected yet:

- `DOCKING_APPROACH` descends straight to the pad. Docking's proposed target will replace this.
- `TRACKING` sends no command, because there is no Navigation target yet.
- A command that Motion rejects is printed, not handled. `context` does not yet report it to Safety (`pending_command_failure`), and has no `operator_abort`.
- Docking's outputs and the bird are still scripted by the demo scenarios.

## Running

Code lives in this folder:

- `state_machine.py`: the `State` enum and `step()`.
- `run_loop.py`: the 10 Hz synthetic loop. It runs a scripted demo through `step()` and sends the matching commands to Motion.
- `demos.py`: the scripted demo scenarios. They script facts about the world (battery, cart, people, comms, pad alignment), not Safety's answers.
- `tests/`: unit tests for `step()`, and one end-to-end test per demo.

Run a demo from the repo root:

```bash
python3 -m state_machine.run_loop full_cycle
```

It prints every state transition with its time and reason. With no name, it runs `full_cycle`.

| Demo | What happens |
|---|---|
| `full_cycle` | Launch for a bird, lose it, return on low battery, wait for the cart, land, recharge |
| `docking_retry` | Docking fails on the first attempt; the mission aborts, retries and lands |
| `emergency` | The battery drops to 8% while tracking; Safety raises an emergency and the drone lands in place |
| `blocked_dock` | The cart keeps moving, so Safety never allows the approach; the drone holds in `DOCKING_INIT` |
| `not_aligned` | The drone is not lined up with the pad; Safety replaces the descent with a hover until it is |
| `cart_during_descent` | The cart starts moving mid-descent; the mission aborts, waits for the cart to stop, then lands |
| `comm_loss` | Communication is lost while tracking; Safety raises an emergency and the drone lands in place |

The command paces the run in real time, so a 10-second demo takes 10 seconds. It also writes the transitions to a new log file in `universal_log/`; do not commit those files.

Run the tests:

```bash
python3 -m pytest state_machine -v
```

The tests call `run_world()` without real-time pacing or logging, so they finish immediately and write no files.

`run_world(duration_ms, scenario=...)` returns a dict:

- `transitions`: `(time_ms, from_state, to_state, reason)` for each state change.
- `commands`: `(time_ms, kind, accepted, reason)` for each new command sent to Motion. A renewed command is listed once.
- `vehicle`: Motion's feedback after the last tick (`grounded`, `armed`, `airborne`, `pose`, …).
