"""Trace checker -- replay a Motion run and check it never broke the rules.

The unit tests check single behaviours ("a hold stops the drone this tick").
This module checks *whole runs*: give it the tick-by-tick trace of a flight
and it walks every pair of consecutive samples looking for anything the
shared contract (INTEGRATION_README.md §5 and §8) says must never happen:

==================  ======================================================
Rule                What it catches
==================  ======================================================
finite_pose         NaN / inf anywhere in the pose
time_monotonic      sample times that repeat or go backwards
below_ground        z < 0
above_ceiling       z above the configured altitude ceiling
outside_geofence    horizontal distance from home beyond the fence radius
horizontal_speed    moved further sideways in one tick than 5 m/s allows
vertical_speed      climbed / descended faster than 2 m/s
yaw_rate            turned faster than 90 deg/s
disarmed_motion     the pose changed while disarmed
ground_flags        `airborne` / `grounded` disagree with z (0.05 m rule)
landed_off_ground   `landing_settled` / status `landed` while not on z = 0
emergency_motion    sideways movement, or descent faster than 1 m/s,
                    during an emergency descent
emergency_release   emergency latch released while still in the air, or
                    still armed after the emergency touchdown
expired_hold_moved  the vehicle moved in a tick whose command had expired
ack_active_id       a rejected command changed what Motion is flying, or
                    an accepted one did not become the active command
==================  ======================================================

Rules only run when the trace carries the fields they need, so the same
checker works on a full recorded `MotionStub` run (JSONL from
`TraceRecorder`) and on the pose-only synthetic CSVs from
`synthetic/generate_motion_data.py`.

Besides violations, every report carries the numbers the December milestone
asks for: path length, peak speeds, time airborne, final landing error from
the pad, and how many commands were rejected and why.

Usage (from the repo root):

    py -3 -m motion_engine.trace_checker motion_engine/motion_logs/*.csv
    py -3 -m motion_engine.trace_checker run.jsonl --json
    py -3 -m motion_engine.trace_checker --demo              # record + check a nominal mission
    py -3 -m motion_engine.trace_checker --demo --save demo.jsonl

Exit code: 0 = every trace clean, 1 = at least one violation, 2 = a file
could not be read.

Recording your own run:

    rec = TraceRecorder(motion)
    rec.snapshot(clock.timestamp_ns)                 # starting pose
    ack = rec.submit(command, clock.timestamp_ns)    # instead of motion.submit
    rec.step(0.1, clock.timestamp_ns)                # instead of motion.step
    clock.advance(0.1)
    report = check_trace(rec.samples, limits=motion.limits, home=motion.home)
    rec.write_jsonl("run.jsonl")
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:  # allow `py -3 motion_engine/trace_checker.py`
    sys.path.insert(0, str(_REPO_ROOT))

from motion_engine.contracts import (  # noqa: E402
    CommandAck,
    CommandStatus,
    Pose,
    Reason,
    VehicleFeedback,
)
from motion_engine.motion_stubs import (  # noqa: E402
    AIRBORNE_THRESHOLD_M,
    GROUND_Z_M,
    MotionLimits,
    MotionStub,
    wrap_180,
)

#: Version of the JSONL trace format written by `TraceRecorder`.
TRACE_SCHEMA_VERSION = 1

#: Every rule name, in the order they are reported.
RULES = (
    "finite_pose",
    "time_monotonic",
    "below_ground",
    "above_ceiling",
    "outside_geofence",
    "horizontal_speed",
    "vertical_speed",
    "yaw_rate",
    "disarmed_motion",
    "ground_flags",
    "landed_off_ground",
    "emergency_motion",
    "emergency_release",
    "expired_hold_moved",
    "ack_active_id",
)


# --------------------------------------------------------------------------
# Trace data
# --------------------------------------------------------------------------


@dataclass
class TraceSample:
    """One tick of a run: the pose after the tick, plus whatever else is known.

    Only `t_ns` and the pose are required. The optional fields come from
    `VehicleFeedback`; `acks` are the acknowledgements Motion returned for
    commands submitted *during* this tick, before it stepped.
    """

    t_ns: int
    x: float
    y: float
    z: float
    yaw_deg: float
    armed: Optional[bool] = None
    airborne: Optional[bool] = None
    grounded: Optional[bool] = None
    emergency_descent: Optional[bool] = None
    landing_settled: Optional[bool] = None
    status: Optional[str] = None
    active_command_id: Optional[str] = None
    has_active_id: bool = False  # active_command_id can legitimately be None
    acks: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def pose(self) -> Pose:
        return Pose(self.x, self.y, self.z, self.yaw_deg)

    @classmethod
    def from_feedback(
        cls, fb: VehicleFeedback, acks: Iterable[CommandAck] = ()
    ) -> "TraceSample":
        p = fb.pose
        return cls(
            t_ns=fb.timestamp_ns,
            x=p.x, y=p.y, z=p.z, yaw_deg=p.yaw_deg,
            armed=fb.armed,
            airborne=fb.airborne,
            grounded=fb.grounded,
            emergency_descent=fb.emergency_descent,
            landing_settled=fb.landing_settled,
            status=fb.status.value if isinstance(fb.status, CommandStatus) else fb.status,
            active_command_id=fb.active_command_id,
            has_active_id=True,
            acks=[a.to_dict() if isinstance(a, CommandAck) else dict(a) for a in acks],
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "t_ns": self.t_ns,
            "pose": {"x": self.x, "y": self.y, "z": self.z, "yaw_deg": self.yaw_deg},
        }
        for name in ("armed", "airborne", "grounded", "emergency_descent",
                     "landing_settled", "status"):
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        if self.has_active_id:
            out["active_command_id"] = self.active_command_id
        if self.acks:
            out["acks"] = self.acks
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TraceSample":
        pose = d["pose"]
        return cls(
            t_ns=int(d["t_ns"]),
            x=float(pose["x"]), y=float(pose["y"]), z=float(pose["z"]),
            yaw_deg=float(pose["yaw_deg"]),
            armed=d.get("armed"),
            airborne=d.get("airborne"),
            grounded=d.get("grounded"),
            emergency_descent=d.get("emergency_descent"),
            landing_settled=d.get("landing_settled"),
            status=d.get("status"),
            active_command_id=d.get("active_command_id"),
            has_active_id="active_command_id" in d,
            acks=list(d.get("acks") or []),
        )


class TraceRecorder:
    """Wraps a `MotionStub` and records one `TraceSample` per tick.

    Use `submit()` / `step()` exactly like the stub's own methods; the acks
    from `submit()` are attached to the sample that the next `step()` writes.
    """

    def __init__(self, motion: MotionStub) -> None:
        self.motion = motion
        self.samples: List[TraceSample] = []
        self._pending_acks: List[CommandAck] = []

    def snapshot(self, now_ns: int) -> TraceSample:
        """Record the current state without stepping (e.g. the starting pose)."""
        sample = TraceSample.from_feedback(self.motion.feedback(now_ns), self._pending_acks)
        self._pending_acks = []
        self.samples.append(sample)
        return sample

    def submit(self, command: Any, now_ns: int) -> CommandAck:
        ack = self.motion.submit(command, now_ns)
        self._pending_acks.append(ack)
        return ack

    def step(self, dt: float, now_ns: int) -> TraceSample:
        """Step Motion once. `now_ns` is the tick's *start* time (what Motion
        uses for expiry); the sample is stamped at the tick's *end*,
        `now_ns + dt`, because that is when the new pose is true."""
        self.motion.step(dt, now_ns=now_ns)
        end_ns = now_ns + int(round(dt * 1e9)) if math.isfinite(dt) else now_ns
        return self.snapshot(end_ns)

    def write_jsonl(self, path) -> Path:
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            header = {"trace_schema_version": TRACE_SCHEMA_VERSION, "source": "TraceRecorder",
                      "frame": "local_enu", "synthetic": True}
            f.write(json.dumps(header) + "\n")
            for s in self.samples:
                f.write(json.dumps(s.to_dict(), allow_nan=True) + "\n")
        return path


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    rule: str
    index: int          # sample index in the trace
    t_ns: int
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": self.rule, "index": self.index, "t_ns": self.t_ns, "message": self.message}


@dataclass
class TraceReport:
    name: str
    samples: int
    violations: List[Violation]
    metrics: Dict[str, Any]
    rules_checked: List[str]

    @property
    def ok(self) -> bool:
        return not self.violations

    def by_rule(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for v in self.violations:
            counts[v.rule] = counts.get(v.rule, 0) + 1
        return counts

    def rule_hits(self, rule: str) -> List[Violation]:
        return [v for v in self.violations if v.rule == rule]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "samples": self.samples,
            "rules_checked": list(self.rules_checked),
            "violation_counts": self.by_rule(),
            "violations": [v.to_dict() for v in self.violations],
            "metrics": self.metrics,
        }

    def format_text(self, max_violations: int = 10) -> str:
        m = self.metrics
        lines = [
            f"{self.name}: {'OK' if self.ok else 'FAIL'} "
            f"({self.samples} samples, {m.get('duration_s', 0.0):.1f} s, "
            f"{len(self.rules_checked)} rules)",
            "  path {:.2f} m | max speed h {:.2f} m/s, v {:.2f} m/s, yaw {:.1f} deg/s"
            " | max alt {:.2f} m | max radius {:.2f} m".format(
                m.get("path_length_m", 0.0), m.get("max_horizontal_speed_mps", 0.0),
                m.get("max_vertical_speed_mps", 0.0), m.get("max_yaw_rate_dps", 0.0),
                m.get("max_altitude_m", 0.0), m.get("max_radius_m", 0.0),
            ),
        ]
        extra = []
        if m.get("airborne_time_s") is not None:
            extra.append(f"airborne {m['airborne_time_s']:.1f} s")
        if m.get("landed") is not None:
            extra.append(f"landed {'yes' if m['landed'] else 'no'}")
        if m.get("landing_error_m") is not None:
            extra.append(f"landing error {m['landing_error_m']:.3f} m")
        if m.get("acks_total"):
            rejected = m.get("rejected_by_reason") or {}
            extra.append(f"acks {m['acks_total']} ({sum(rejected.values())} rejected"
                         + (": " + ", ".join(f"{k} x{v}" for k, v in sorted(rejected.items()))
                            if rejected else "") + ")")
        if m.get("expired_hold_ticks"):
            extra.append(f"expired-hold ticks {m['expired_hold_ticks']}")
        if extra:
            lines.append("  " + " | ".join(extra))
        for v in self.violations[:max_violations]:
            lines.append(f"  ! [{v.rule}] sample {v.index} (t={v.t_ns / 1e9:.2f} s): {v.message}")
        if len(self.violations) > max_violations:
            lines.append(f"  ... {len(self.violations) - max_violations} more violations")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# The checker
# --------------------------------------------------------------------------


def _finite(*values: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)


def check_trace(
    samples: Sequence[TraceSample],
    *,
    limits: Optional[MotionLimits] = None,
    home: Pose = Pose(0.0, 0.0, 0.0, 0.0),
    pad: Optional[Pose] = None,
    name: str = "trace",
    tol_m: float = 1e-3,
    tol_deg: float = 1e-2,
) -> TraceReport:
    """Check every sample and every consecutive pair; return a `TraceReport`.

    `limits` default to `MotionLimits()` -- the INTEGRATION_README §5 table.
    `pad` (default `home`) is where landing error is measured from.
    `tol_m` / `tol_deg` absorb float noise and the 4-decimal rounding in the
    synthetic CSVs; they are far below anything that would matter.
    """
    lim = limits if limits is not None else MotionLimits()
    pad = home if pad is None else pad
    out: List[Violation] = []
    checked: set = set()

    def flag(rule: str, i: int, message: str) -> None:
        out.append(Violation(rule, i, samples[i].t_ns, message))

    path = 0.0
    max_h = max_v = max_yaw = 0.0
    max_alt = 0.0
    max_r = 0.0
    airborne_ns = 0
    expired_ticks = 0
    acks_total = 0
    rejected: Dict[str, int] = {}

    for i, s in enumerate(samples):
        # ---- single-sample rules ------------------------------------------
        checked.add("finite_pose")
        if not _finite(s.x, s.y, s.z, s.yaw_deg):
            flag("finite_pose", i, f"pose is not finite: {s.pose}")
            continue  # every geometric rule below would be meaningless

        checked.update(("below_ground", "above_ceiling", "outside_geofence"))
        if s.z < GROUND_Z_M - tol_m:
            flag("below_ground", i, f"z = {s.z:.3f} m is below the ground")
        if s.z > lim.max_altitude_m + tol_m:
            flag("above_ceiling", i, f"z = {s.z:.3f} m is above the {lim.max_altitude_m} m ceiling")
        r = math.hypot(s.x - home.x, s.y - home.y)
        if r > lim.geofence_radius_m + tol_m:
            flag("outside_geofence", i, f"{r:.2f} m from home, fence is {lim.geofence_radius_m} m")
        max_alt = max(max_alt, s.z)
        max_r = max(max_r, r)

        if s.airborne is not None and s.grounded is not None:
            checked.add("ground_flags")
            expect_airborne = s.z > GROUND_Z_M + AIRBORNE_THRESHOLD_M
            if s.airborne != expect_airborne or s.grounded == s.airborne:
                flag("ground_flags", i,
                     f"airborne={s.airborne}, grounded={s.grounded} at z = {s.z:.3f} m")

        if s.landing_settled is not None or s.status is not None:
            checked.add("landed_off_ground")
            landed = s.landing_settled is True or s.status == CommandStatus.LANDED.value
            if landed and (abs(s.z - GROUND_Z_M) > tol_m or s.airborne is True):
                flag("landed_off_ground", i, f"reports landed at z = {s.z:.3f} m")
            if s.status == CommandStatus.LANDED.value and s.landing_settled is False:
                flag("landed_off_ground", i, "status 'landed' but landing_settled is False")

        if s.status == CommandStatus.EXPIRED_HOLD.value:
            expired_ticks += 1
        for ack in s.acks:
            acks_total += 1
            if not ack.get("accepted"):
                reason = str(ack.get("reason"))
                rejected[reason] = rejected.get(reason, 0) + 1

        if i == 0:
            continue
        p = samples[i - 1]
        if not _finite(p.x, p.y, p.z, p.yaw_deg):
            continue

        # ---- pair rules ---------------------------------------------------
        checked.add("time_monotonic")
        dt_ns = s.t_ns - p.t_ns
        if dt_ns <= 0:
            flag("time_monotonic", i, f"time went from {p.t_ns} ns to {s.t_ns} ns")
            continue
        dt = dt_ns / 1e9

        dh = math.hypot(s.x - p.x, s.y - p.y)
        dz = s.z - p.z
        dyaw = abs(wrap_180(s.yaw_deg - p.yaw_deg))
        path += math.sqrt(dh * dh + dz * dz)
        max_h = max(max_h, dh / dt)
        max_v = max(max_v, abs(dz) / dt)
        max_yaw = max(max_yaw, dyaw / dt)
        if p.airborne is True or (p.airborne is None and p.z > AIRBORNE_THRESHOLD_M):
            airborne_ns += dt_ns

        checked.update(("horizontal_speed", "vertical_speed", "yaw_rate"))
        if dh > lim.max_horizontal_speed_mps * dt + tol_m:
            flag("horizontal_speed", i,
                 f"moved {dh:.3f} m sideways in {dt:.2f} s ({dh / dt:.2f} m/s > "
                 f"{lim.max_horizontal_speed_mps} m/s)")
        if abs(dz) > lim.max_vertical_speed_mps * dt + tol_m:
            flag("vertical_speed", i,
                 f"moved {dz:+.3f} m vertically in {dt:.2f} s ({abs(dz) / dt:.2f} m/s > "
                 f"{lim.max_vertical_speed_mps} m/s)")
        if dyaw > lim.max_yaw_rate_dps * dt + tol_deg:
            flag("yaw_rate", i,
                 f"turned {dyaw:.2f} deg in {dt:.2f} s ({dyaw / dt:.1f} deg/s > "
                 f"{lim.max_yaw_rate_dps} deg/s)")

        moved = dh > tol_m or abs(dz) > tol_m or dyaw > tol_deg

        if p.armed is False and s.armed is False:
            checked.add("disarmed_motion")
            if moved:
                flag("disarmed_motion", i, "pose changed while disarmed")

        if p.emergency_descent is not None and s.emergency_descent is not None:
            checked.update(("emergency_motion", "emergency_release"))
            # The tick an emergency starts in (accepted before the step) and
            # the touchdown tick are both flown at the emergency rate.
            if p.emergency_descent or s.emergency_descent:
                if dh > tol_m:
                    flag("emergency_motion", i, f"moved {dh:.3f} m sideways during emergency descent")
                if -dz > lim.emergency_descent_mps * dt + tol_m:
                    flag("emergency_motion", i,
                         f"descended {-dz / dt:.2f} m/s, emergency rate is "
                         f"{lim.emergency_descent_mps} m/s")
                if dz > tol_m:
                    flag("emergency_motion", i, f"climbed {dz:.3f} m during emergency descent")
                if p.emergency_descent and not s.emergency_descent:
                    if abs(s.z - GROUND_Z_M) > tol_m:
                        flag("emergency_release", i,
                             f"emergency latch released at z = {s.z:.3f} m")
                    if s.armed is True:
                        flag("emergency_release", i, "still armed after emergency touchdown")

        if s.status is not None:
            checked.add("expired_hold_moved")
            if s.status == CommandStatus.EXPIRED_HOLD.value and moved:
                flag("expired_hold_moved", i,
                     f"command had expired but the vehicle moved {math.sqrt(dh * dh + dz * dz):.3f} m")

        if s.acks and p.has_active_id:
            checked.add("ack_active_id")
            running = p.active_command_id
            for ack in s.acks:
                active = ack.get("active_command_id")
                if not ack.get("accepted"):
                    if active != running:
                        flag("ack_active_id", i,
                             f"rejected {ack.get('command_id')!r} ({ack.get('reason')}) but active "
                             f"changed {running!r} -> {active!r}")
                elif ack.get("reason") == Reason.ACCEPTED and active != ack.get("command_id"):
                    flag("ack_active_id", i,
                         f"accepted {ack.get('command_id')!r} but active is {active!r}")
                running = active

    last = samples[-1] if samples else None
    duration = (last.t_ns - samples[0].t_ns) / 1e9 if samples else 0.0
    landed: Optional[bool] = None
    landing_error: Optional[float] = None
    if last is not None and _finite(last.x, last.y, last.z):
        if last.landing_settled is not None:
            landed = bool(last.landing_settled)
        elif last.status is not None:
            landed = last.status == CommandStatus.LANDED.value
        on_ground = abs(last.z - GROUND_Z_M) <= tol_m
        if on_ground:
            landing_error = math.hypot(last.x - pad.x, last.y - pad.y)

    metrics = {
        "duration_s": round(duration, 6),
        "path_length_m": round(path, 4),
        "max_horizontal_speed_mps": round(max_h, 4),
        "max_vertical_speed_mps": round(max_v, 4),
        "max_yaw_rate_dps": round(max_yaw, 3),
        "max_altitude_m": round(max_alt, 4),
        "max_radius_m": round(max_r, 4),
        "airborne_time_s": round(airborne_ns / 1e9, 6),
        "final_pose": last.to_dict()["pose"] if last is not None else None,
        "landed": landed,
        "landing_error_m": round(landing_error, 4) if landing_error is not None else None,
        "acks_total": acks_total,
        "rejected_by_reason": rejected,
        "expired_hold_ticks": expired_ticks,
    }
    return TraceReport(
        name=name,
        samples=len(samples),
        violations=out,
        metrics=metrics,
        rules_checked=[r for r in RULES if r in checked],
    )


# --------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------


def load_jsonl(path) -> List[TraceSample]:
    """Read a trace written by `TraceRecorder.write_jsonl()`."""
    samples: List[TraceSample] = []
    with Path(path).open(encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if "trace_schema_version" in record:
                if record["trace_schema_version"] != TRACE_SCHEMA_VERSION:
                    raise ValueError(f"{path}:{n}: unsupported trace_schema_version "
                                     f"{record['trace_schema_version']}")
                continue
            samples.append(TraceSample.from_dict(record))
    return samples


def load_synthetic_csv(path) -> List[TraceSample]:
    """Read a CSV from `synthetic/generate_motion_data.py` (pose only).

    `# key=value` metadata lines at the top are skipped. The CSV has no
    armed/airborne flags, so only the geometric rules run on it.
    """
    with Path(path).open(newline="", encoding="utf-8") as f:
        body = [line for line in f.read().splitlines() if not line.startswith("#")]
    samples = []
    for row in csv.DictReader(body):
        samples.append(TraceSample(
            t_ns=int(row["timestamp_ns"]),
            x=float(row["x_m"]), y=float(row["y_m"]), z=float(row["z_m"]),
            yaw_deg=float(row["yaw_deg"]),
        ))
    return samples


def load_trace(path) -> List[TraceSample]:
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return load_synthetic_csv(path)
    if suffix in (".jsonl", ".json", ".ndjson"):
        return load_jsonl(path)
    raise ValueError(f"{path}: expected a .csv (synthetic generator) or .jsonl (TraceRecorder) file")


# --------------------------------------------------------------------------
# Demo mission -- a nominal run recorded straight from MotionStub
# --------------------------------------------------------------------------


def record_demo_mission() -> TraceRecorder:
    """Fly the README's nominal cycle through MotionStub and record it.

    Launch to 5 m, track a bird 30 m to the north-east (renewed every tick),
    return to the 5 m approach point over the pad, descend, land, disarm.
    Commands go through `submit()` exactly as the coordinator will send them.
    """
    from motion_engine.contracts import Command, MotionCommandType as K, SimulationClock

    clock = SimulationClock()
    motion = MotionStub(clock=clock)
    rec = TraceRecorder(motion)
    validity = 200_000_000
    counter = [0]

    def cmd(kind, target=None, lifecycle=False, cid=None):
        if cid is None:
            counter[0] += 1
            cid = f"demo-{counter[0]}"
        now = clock.timestamp_ns
        return Command(command_id=cid, kind=kind, mission_state="DEMO", issued_ns=now,
                       expires_ns=None if lifecycle else now + validity,
                       source="trace_checker.demo", reason="nominal", target=target)

    def tick(c=None):
        if c is not None:
            rec.submit(c, clock.timestamp_ns)
        rec.step(0.1, clock.timestamp_ns)
        clock.advance(0.1)

    rec.snapshot(clock.timestamp_ns)
    tick(cmd(K.ARM, lifecycle=True))
    tick(cmd(K.TAKEOFF, Pose(0, 0, 5, 0), lifecycle=True))
    while motion.pose.z < 5.0:
        tick()

    def fly(kind, target, until, max_ticks=600):
        cid = None
        for _ in range(max_ticks):
            c = cmd(kind, target, cid=cid)
            cid = c.command_id
            tick(c)
            if until():
                return
        raise RuntimeError(f"demo: {kind} never finished")

    track = Pose(15.0, 15.0, 5.0, 45.0)
    fly(K.TRACK_TARGET, track, lambda: motion.pose == track)
    for _ in range(20):  # hold the standoff for 2 s
        tick(cmd(K.HOVER))
    approach = Pose(0.0, 0.0, 5.0, 0.0)
    fly(K.GOTO_DOCK_APPROACH, approach, lambda: motion.pose == approach)
    fly(K.DESCEND_TO_DOCK, Pose(0.0, 0.0, 0.0, 0.0), lambda: motion.landing_settled)
    tick(cmd(K.DISARM, lifecycle=True))
    tick()
    return rec


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m motion_engine.trace_checker",
        description="Check Motion traces against the INTEGRATION_README limits and rules.",
    )
    ap.add_argument("files", nargs="*", help=".jsonl (TraceRecorder) or .csv (synthetic generator)")
    ap.add_argument("--demo", action="store_true", help="record and check a nominal MotionStub mission")
    ap.add_argument("--save", type=Path, help="with --demo: also write the recorded trace as JSONL")
    ap.add_argument("--json", action="store_true", help="print the reports as JSON")
    ap.add_argument("--tol", type=float, default=1e-3, help="position tolerance in metres (default 0.001)")
    ap.add_argument("--max-violations", type=int, default=10, help="violations shown per trace (text mode)")
    args = ap.parse_args(argv)

    if not args.files and not args.demo:
        ap.error("give at least one trace file, or --demo")

    reports: List[TraceReport] = []
    status = 0
    if args.demo:
        rec = record_demo_mission()
        if args.save:
            rec.write_jsonl(args.save)
        reports.append(check_trace(rec.samples, limits=rec.motion.limits, home=rec.motion.home,
                                   name="demo_mission", tol_m=args.tol))
    files: List[str] = []
    for pattern in args.files:  # Windows shells do not expand *.csv
        matches = sorted(glob.glob(pattern)) if any(ch in pattern for ch in "*?[") else []
        files.extend(matches or [pattern])
    for f in files:
        try:
            samples = load_trace(f)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"error: could not read {f}: {e}", file=sys.stderr)
            status = 2
            continue
        reports.append(check_trace(samples, name=str(f), tol_m=args.tol))

    if args.json:
        print(json.dumps([r.to_dict() for r in reports], indent=2))
    else:
        for r in reports:
            print(r.format_text(args.max_violations))
        clean = sum(r.ok for r in reports)
        print(f"\n{clean}/{len(reports)} traces clean")
    if status == 0 and not all(r.ok for r in reports):
        status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
