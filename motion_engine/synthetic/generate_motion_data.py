"""Synthetic motion data for the Motion Engine -- simple, readable scenarios.

Each scenario is a short list of (direction, seconds) moves -- "go up for 2 s,
go left for 3 s, spin right for 4 s" -- played through a very simple model:

* The drone moves at a constant speed while a direction is held
  (1 m/s sideways/forward, 0.5 m/s up/down, 45 deg/s yaw) and stops dead
  when the move ends. No drag, no wind, no overshoot -- easy to read.
* The motor columns come straight from the real stub mixer,
  `commands.motor_commands.direction_to_motor_command`, so the data matches
  what the Motion Engine itself would output for each direction.

Frame (same as motion_stubs.py): x = east, y = north, z = up (metres),
yaw in degrees, 0 = facing east, counter-clockwise positive.
FORWARD/BACKWARD/LEFT/RIGHT are relative to where the drone is facing, so
after a 90 deg yaw-left, "forward" flies north instead of east.

Usage (from the repo root):
    py -3 motion_engine/synthetic/generate_motion_data.py            # all scenarios
    py -3 motion_engine/synthetic/generate_motion_data.py --noise 0.02
    py -3 motion_engine/synthetic/generate_motion_data.py --rate 20 --out some/folder

Outputs one CSV per scenario, plus a PNG plot if matplotlib is installed.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

_MOTION_ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(_MOTION_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MOTION_ENGINE_ROOT))

from commands.motor_commands import Direction, direction_to_motor_command  # noqa: E402

D = Direction

# --------------------------------------------------------------------------
# Speeds -- change these to make the drone faster or slower.
# --------------------------------------------------------------------------
HORIZONTAL_SPEED_MPS = 1.0   # forward / backward / left / right
VERTICAL_SPEED_MPS = 0.5     # up / down
YAW_RATE_DPS = 45.0          # yaw_left / yaw_right

# --------------------------------------------------------------------------
# Scenarios -- each is a list of (direction, how many seconds to hold it).
# Every scenario starts on the ground at (0, 0, 0) facing east.
# --------------------------------------------------------------------------
SCENARIOS: Dict[str, List[Tuple[Direction, float]]] = {
    # Climb 2 m, pause, come back down.
    "up_down": [
        (D.HOVER, 1), (D.UP, 4), (D.HOVER, 2), (D.DOWN, 4), (D.HOVER, 1),
    ],
    # Take off, slide 3 m left, 3 m back right, land.
    "left_right": [
        (D.UP, 2), (D.HOVER, 1), (D.LEFT, 3), (D.HOVER, 1),
        (D.RIGHT, 3), (D.HOVER, 1), (D.DOWN, 2),
    ],
    # Take off, fly 3 m forward, 3 m back, land.
    "forward_backward": [
        (D.UP, 2), (D.HOVER, 1), (D.FORWARD, 3), (D.HOVER, 1),
        (D.BACKWARD, 3), (D.HOVER, 1), (D.DOWN, 2),
    ],
    # Take off, spin a full circle left (8 s x 45 deg/s = 360), then right, land.
    "rotate": [
        (D.UP, 2), (D.HOVER, 1), (D.YAW_LEFT, 8), (D.HOVER, 1),
        (D.YAW_RIGHT, 8), (D.HOVER, 1), (D.DOWN, 2),
    ],
    # Fly a 3 m square by turning 90 deg left at each corner -- shows that
    # "forward" follows the heading.
    "square": [
        (D.UP, 2), (D.HOVER, 1),
        (D.FORWARD, 3), (D.YAW_LEFT, 2),
        (D.FORWARD, 3), (D.YAW_LEFT, 2),
        (D.FORWARD, 3), (D.YAW_LEFT, 2),
        (D.FORWARD, 3), (D.YAW_LEFT, 2),
        (D.HOVER, 1), (D.DOWN, 2),
    ],
    # Everything once, in order.
    "full_tour": [
        (D.HOVER, 1), (D.UP, 4), (D.HOVER, 1),
        (D.FORWARD, 2), (D.BACKWARD, 2), (D.LEFT, 2), (D.RIGHT, 2),
        (D.UP, 2), (D.DOWN, 2),
        (D.YAW_LEFT, 2), (D.YAW_RIGHT, 2),
        (D.HOVER, 1), (D.DOWN, 4), (D.HOVER, 1),
    ],
}

COLUMNS = [
    "t_s", "step", "direction",
    "x_m", "y_m", "z_m", "yaw_deg",
    "vx_mps", "vy_mps", "vz_mps", "yaw_rate_dps",
    "motor_fl", "motor_fr", "motor_rl", "motor_rr",
]


def _velocity(direction: Direction, yaw_deg: float) -> Tuple[float, float, float, float]:
    """World-frame (vx, vy, vz, yaw_rate) for holding `direction` at `yaw_deg`."""
    fwd, left, up, yaw_rate = 0.0, 0.0, 0.0, 0.0
    if direction == D.FORWARD:
        fwd = HORIZONTAL_SPEED_MPS
    elif direction == D.BACKWARD:
        fwd = -HORIZONTAL_SPEED_MPS
    elif direction == D.LEFT:
        left = HORIZONTAL_SPEED_MPS
    elif direction == D.RIGHT:
        left = -HORIZONTAL_SPEED_MPS
    elif direction == D.UP:
        up = VERTICAL_SPEED_MPS
    elif direction == D.DOWN:
        up = -VERTICAL_SPEED_MPS
    elif direction == D.YAW_LEFT:
        yaw_rate = YAW_RATE_DPS
    elif direction == D.YAW_RIGHT:
        yaw_rate = -YAW_RATE_DPS
    # Rotate body (forward, left) into world (east, north).
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    return fwd * c - left * s, fwd * s + left * c, up, yaw_rate


def generate(moves: List[Tuple[Direction, float]], rate_hz: float = 10.0,
             noise_m: float = 0.0, seed: int = 0) -> List[dict]:
    """Play `moves` through the simple model; return one dict per sample."""
    rng = random.Random(seed)
    dt = 1.0 / rate_hz
    x = y = z = yaw = 0.0
    t = 0.0
    rows: List[dict] = []

    def emit(step: int, direction: Direction, v: Tuple[float, float, float, float]) -> None:
        motors = direction_to_motor_command(direction)
        n = (lambda: rng.gauss(0.0, noise_m)) if noise_m > 0 else (lambda: 0.0)
        rows.append({
            "t_s": round(t, 3), "step": step, "direction": direction.value,
            "x_m": round(x + n(), 4) + 0.0, "y_m": round(y + n(), 4) + 0.0,
            "z_m": round(max(0.0, z + n()), 4), "yaw_deg": round(yaw % 360.0, 2),
            "vx_mps": round(v[0], 4) + 0.0, "vy_mps": round(v[1], 4) + 0.0,
            "vz_mps": round(v[2], 4), "yaw_rate_dps": round(v[3], 2),
            "motor_fl": motors.front_left, "motor_fr": motors.front_right,
            "motor_rl": motors.rear_left, "motor_rr": motors.rear_right,
        })

    for step, (direction, seconds) in enumerate(moves):
        ticks = int(round(seconds * rate_hz))
        for _ in range(ticks):
            v = _velocity(direction, yaw)
            emit(step, direction, v)
            x += v[0] * dt
            y += v[1] * dt
            z = max(0.0, z + v[2] * dt)   # can't go through the ground
            yaw += v[3] * dt
            t += dt
    # Final resting sample so the last position is in the file.
    emit(len(moves), D.HOVER, (0.0, 0.0, 0.0, 0.0))
    return rows


def write_csv(rows: List[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def plot(all_rows: Dict[str, List[dict]], path: Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    names = list(all_rows)
    fig, axes = plt.subplots(len(names), 2, figsize=(11, 2.6 * len(names)))
    for i, name in enumerate(names):
        r = all_rows[name]
        t = [row["t_s"] for row in r]
        a = axes[i][0]
        for key, label in (("x_m", "x (east)"), ("y_m", "y (north)"), ("z_m", "z (up)")):
            a.plot(t, [row[key] for row in r], label=label)
        a.set_title(f"{name}: position")
        a.set_ylabel("m")
        a.legend(fontsize=7, loc="upper right")
        b = axes[i][1]
        b.plot(t, [row["yaw_deg"] for row in r], color="tab:purple")
        b.set_title(f"{name}: heading")
        b.set_ylabel("yaw (deg)")
        b.set_ylim(-10, 370)
    for a in axes[-1]:
        a.set_xlabel("time (s)")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return True


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "data")
    p.add_argument("--rate", type=float, default=10.0, help="samples per second (default 10)")
    p.add_argument("--noise", type=float, default=0.0,
                   help="std-dev of position noise in metres (default 0 = perfectly clean)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("scenarios", nargs="*", help=f"subset of: {', '.join(SCENARIOS)}")
    args = p.parse_args()

    names = args.scenarios or list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        sys.exit(f"Unknown scenario(s): {unknown}. Choose from {list(SCENARIOS)}")

    args.out.mkdir(parents=True, exist_ok=True)
    all_rows = {}
    for name in names:
        rows = generate(SCENARIOS[name], args.rate, args.noise, args.seed)
        write_csv(rows, args.out / f"{name}.csv")
        all_rows[name] = rows
        end = rows[-1]
        print(f"{name:17s} {len(rows):4d} rows, {end['t_s']:5.1f} s, ends at "
              f"x={end['x_m']:+.2f} y={end['y_m']:+.2f} z={end['z_m']:+.2f} yaw={end['yaw_deg']:.0f}")
    if plot(all_rows, args.out / "overview.png"):
        print(f"plot -> {args.out / 'overview.png'}")


if __name__ == "__main__":
    main()
