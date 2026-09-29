# Synthetic motion data

Simple, hand-readable flight data for the Motion Engine: the drone going up,
down, left, right, forward, back, and spinning in place.

```bash
py -3 motion_engine/synthetic/generate_motion_data.py              # all scenarios -> motion_engine/motion_logs/
py -3 motion_engine/synthetic/generate_motion_data.py rotate square
py -3 motion_engine/synthetic/generate_motion_data.py --noise 0.02 # add a little sensor jitter
```

## Scenarios

Output goes to `motion_engine/motion_logs/` (one CSV per scenario + `overview.png`).


| File | What the drone does |
|---|---|
| `up_down.csv` | Climbs 2 m, pauses, comes back down |
| `left_right.csv` | Takes off, slides 3 m left, 3 m back right, lands |
| `forward_backward.csv` | Takes off, flies 3 m forward, 3 m back, lands |
| `rotate.csv` | Takes off, spins a full 360° left, then 360° right, lands |
| `square.csv` | Flies a 3 m square, turning 90° left at each corner |
| `full_tour.csv` | Every direction once, in order |

To make a new one, add a list of `(Direction, seconds)` to `SCENARIOS` in the script.

## The model (deliberately simple)

- Constant speed while a direction is held: **1 m/s** horizontal, **0.5 m/s** vertical, **45°/s** yaw. Stops instantly when the move ends.
- Forward/back/left/right are **relative to where the drone faces** — after a 90° yaw-left, "forward" goes north.
- Motor columns come from the real mixer, `commands/motor_commands.direction_to_motor_command`.
- Frame matches `motion_stubs.py`: x = east, y = north, z = up (m); yaw 0 = east, counter-clockwise positive.

## Columns

| Column | Meaning |
|---|---|
| `t_s` | time (s), 10 samples per second by default |
| `step` | index of the move in the scenario |
| `direction` | the `Direction` being held (`hover`, `up`, `yaw_left`, …) |
| `x_m`, `y_m`, `z_m` | position (m) |
| `yaw_deg` | heading, 0–360 |
| `vx_mps`, `vy_mps`, `vz_mps`, `yaw_rate_dps` | velocity being applied this sample |
| `motor_fl`, `motor_fr`, `motor_rl`, `motor_rr` | stub throttle per motor (0–100, hover = 50) |
