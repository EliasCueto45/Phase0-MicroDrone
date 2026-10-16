# Motion Engine — Phase 0

[Phase 0 scope: Start Here](../START_HERE.md) · [Shared integration contract](../INTEGRATION_README.md)

## Current milestone: the synthetic loop

For the integration milestone there is no drone and no PX4 in the loop.
Motion's job is the kinematic stub, [`motion_stubs.py`](motion_stubs.py),
driven by the central coordinator through the contract in
[INTEGRATION_README.md](../INTEGRATION_README.md) §3-§5. Motion owns the
synthetic vehicle pose and its execution status, and never a mission state.

### Contract (`motion_engine/contracts.py`)

| Type | Direction | What it carries |
|---|---|---|
| `Command` | coordinator → Motion | `command_id`, `kind`, `mission_state`, `target` (`Pose`, local ENU), `frame`, optional speed caps, `issued_ns`, `expires_ns`, `source`, `reason` |
| `CommandAck` | Motion → coordinator, immediately | `command_id`, `accepted`, stable `reason`, `active_command_id` (what is still flying after this) |
| `VehicleFeedback` | Motion → snapshot `vehicle` section | pose, `armed`, `airborne`, `grounded`, `emergency_descent`, `landing_settled`, active command ID/kind/target, `status`, `arrived`, errors, `timestamp_ns`, `valid` |

One coordinator tick:

```python
from motion_engine.contracts import Command, MotionCommandType as K, Pose, SimulationClock
from motion_engine.motion_stubs import MotionStub

clock = SimulationClock()                 # integer ns, starts at 0
motion = MotionStub(logger=shared_logger, clock=clock)

ack = motion.submit(command, clock.timestamp_ns)   # step 8: dispatch, record ack
motion.step(0.1, now_ns=clock.timestamp_ns)        # advance Motion exactly once
vehicle = motion.feedback(clock.timestamp_ns)      # post-motion feedback
clock.advance(0.1)
```

Rules Motion enforces:

- **Accepted is not done.** `status` goes `in_progress` → `arrived`, and for
  landing commands → `landed`. `arrived` uses the 0.25 m arrival tolerance and
  can be true while still airborne, so docking must check `landing_settled`
  (z exactly 0 after a landing command), never `arrived`.
- **Expiry.** Every command except arm/disarm/takeoff/land/emergency needs
  `expires_ns`. Re-sending the active `command_id` with a later expiry renews
  it: no restart, no new log line. If it expires, Motion replaces it with a
  hold at the current pose *before* moving that tick (`status = expired_hold`).
- **Replacement.** An accepted command replaces the active target
  immediately, so a hold sent this tick stops the drone this tick.
- **No silent clamps.** A target above the ceiling or outside the geofence is
  rejected (`target_outside_limits`), not clamped. The direct methods still
  clamp, for scripts.
- **Emergency latch.** After `EMERGENCY_LAND` every other command is rejected
  (`emergency_descent_active`), repeats are idempotent, emergency never
  expires, and touchdown auto-disarms.
- **Bad input is a result, not an exception.** Missing target or expiry, NaN
  or inf, wrong frame or schema, future timestamps and reused IDs each come
  back as a rejected ack with a stable reason (`contracts.Reason`).

Limits default to the INTEGRATION_README §5 table (`MotionLimits`): 5 / 2 m/s,
90 deg/s, 150 m geofence, 30 m ceiling, 0.25 m / 3 deg tolerances, 1 m/s
emergency descent. Pass the same `MotionLimits` that Safety uses.

Logging goes through any object with the agreed
`log(module, event, *, fields, state, truth, decision, t)` method
(`contracts.LogSink`). To write into the shared logger in
[`universal_log/Universal_log.py`](../universal_log/Universal_log.py), the same
one CV uses, pass `UniversalLogSink` from
[`universal_logging.py`](universal_logging.py):

```python
from motion_engine.universal_logging import UniversalLogSink

motion = MotionStub(logger=UniversalLogSink(), clock=clock)
motion.set_log_context(state=state.value)   # coordinator, every tick
```

Each record becomes `State` = the coordinator's mission state (`IDLE` until
one is set, as in CV) and `Details` = `module`, `event`, `t`, `fields`,
`synthetic_truth`, `decision` (the same keys as `LogEntry.to_dict()`).
UniversalLog's outer timestamp is wall-clock emission time; Motion's clock
reading stays in `Details["t"]` and is the one to use for ordering. CV and
Motion records land in the same `universal_log/logged_states_<run>.log`.
`contracts.MemoryLogSink` remains the in-memory sink for tests. Motion no
longer imports the old `mission.logging_format`.

### Runnable checks

```bash
py -3 -m pytest motion_engine/tests/test_motion_stubs.py motion_engine/tests/test_motion_contract.py motion_engine/tests/test_universal_logging.py
py -3 motion_engine/synthetic/generate_motion_data.py      # synthetic CSVs, see synthetic/README.md
```

`test_motion_contract.py` covers the README's Motion deliverables: approach
and descent, cancellation, ordinary disarm, emergency-latch interaction,
expiry and renewal, rejected input, and identical traces from identical inputs.

### Failure injection

```bash
py -3 -m pytest motion_engine/tests/test_failure_injection.py -v
```

Injects the START_HERE "definition of done" failures into a running stub and
checks Motion's outcome for each:

| Section | Failures injected | Outcome checked |
|---|---|---|
| A. Command loss | renewals stop mid-move/track/approach/yaw/descent; one dropped renewal; late renewal after expiry; lifecycle and emergency commands with no renewal | holds within one 0.2 s validity window and never moves again; one dropped tick is tolerated; an expired ID cannot be revived; takeoff/land/emergency still complete |
| B. Loop stalls / clock | 1-5 s coordinator stall (incl. one 5 s `dt`); clock running backwards | expires *before* moving; a backwards clock cannot revive a target |
| C. Stale / replayed | late already-expired command; replayed old ID; same ID with a new target | rejected with a stable reason, current target keeps flying |
| D. Geofence | bird walking out of the fence; ceiling and fence edges; out-of-limit target through Safety | never leaves the fence; Safety's hold applies before that tick's movement |
| E. Emergency | `EMERGENCY_LAND` during climb, tracking, approach, descent, hover; on the pad; disarmed | descends in place at 1 m/s, latches, auto-disarms |
| F. Safety hazards | cart moving during descent; hold forbidden; low battery; critical battery mid-approach | descent frozen that tick and resumed under a new ID; lands in place; return still allowed; emergency beats docking |
| G. Garbage input | 19 kinds of malformed command submitted every tick | the flown path is identical to a clean run |
| H. Not a landing | link lost 0.2 m above the pad (inside arrival tolerance) | never `landing_settled`, disarm refused |
| I. Bad `dt` | 0, negative, NaN, inf | NaN/inf are a **known bug**, pinned as strict `xfail` |

Every scenario is recorded and run through the trace checker below, so no
test can pass while breaking a speed, fence or latch rule along the way.

### Trace checker

[`trace_checker.py`](trace_checker.py) walks a whole run tick by tick and
checks 15 rules from INTEGRATION_README §5/§8: finite pose, monotonic time,
ground/ceiling/geofence, horizontal/vertical/yaw rate limits, no motion
while disarmed, airborne/grounded flags, no landing above the ground,
emergency descent in place at 1 m/s, latch release only on the ground, no
motion after expiry, and that rejected commands never change the active
command. It also reports path length, peak speeds, time airborne, landing
error from the pad, and rejected commands by reason.

```bash
py -3 -m motion_engine.trace_checker --demo                          # record + check a nominal mission
py -3 -m motion_engine.trace_checker --demo --save motion_engine/motion_logs/demo.jsonl
py -3 -m motion_engine.trace_checker motion_engine/motion_logs/*.csv  # the synthetic CSVs (pose-only rules)
py -3 -m motion_engine.trace_checker run.jsonl --json
py -3 -m pytest motion_engine/tests/test_trace_checker.py
```

Exit code 0 = all clean, 1 = violations, 2 = unreadable file. Record your
own run by wrapping the stub in `TraceRecorder` (example in the module
docstring).

## Phase-1 (PX4) goals

The original PX4 plan. It comes after the synthetic milestone above.

### Purpose

Translate permitted high-level movement targets into PX4 external-control commands. PX4 supplies low-level flight stabilization in simulation. Building a replacement flight PID or directly driving motors is not required for this semester.

### Inputs and outputs

- Inputs: navigation/docking targets, estimated vehicle state, safety decisions.
- Outputs: bounded PX4 position or velocity targets and yaw commands; command/status logs.
- Define units, coordinate frames, command expiration, and external-control lifecycle before connecting modules.
- Log requested and sent targets separately from observed vehicle motion.

### First tasks

1. Establish a PX4 connection and read status/telemetry.
2. Reproduce takeoff, hold, and landing in the stock simulation.
3. Define a bounded command interface with navigation and safety.
4. Handle rejected commands, stale requests, and loss of the control connection.
5. Execute waypoint and docking targets through the same interface.

Maintain the command stream required by the selected PX4 interface and verify its loss-of-control behavior. Start from the [PX4 offboard example](https://docs.px4.io/main/en/ros2/offboard_control), using documentation matching the pinned release.

### Acceptance evidence

A repeatable flight script takes off, holds, and lands while recording targets and telemetry. Tests demonstrate bounds enforcement, command expiration, and the chosen abort behavior.

A controlled mission abort and motor termination are distinct actions. Do not implement one ambiguous “kill switch” for both.

The PX4 side (offboard connection, SITL flight script) is not part of the
synthetic milestone. Each `MotionStub` method has a `# PHASE-1 HOOK:` comment
naming the PX4 command it becomes; `grep -n "PHASE-1 HOOK" motion_engine/motion_stubs.py`
is the to-do list.
