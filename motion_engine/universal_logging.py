"""Bridge MotionStub's `LogSink` interface to the shared UniversalLog.

MotionStub logs through `log(module, event, *, fields, state, truth,
decision, t)` (see `contracts.LogSink`). The repository's shared logger,
`universal_log/Universal_log.py`, takes one dictionary per record instead:
`{"State": <mission state>, "Details": {...}}`. `UniversalLogSink` converts
the first into the second, so Motion records land in the same run file as
CV's:

    from motion_engine.universal_logging import UniversalLogSink

    motion = MotionStub(logger=UniversalLogSink(), clock=clock)
    motion.set_log_context(state=current_state.value)   # each coordinator tick

Record layout (the same keys as `contracts.LogEntry.to_dict()`):

    State   -- the coordinator's mission state from `set_log_context(state=...)`.
               Defaults to "IDLE" until the coordinator sets one, matching CV.
    Details -- {"module": "MOTION", "event", "t", "fields",
                "synthetic_truth", "decision"}

UniversalLog stamps the outer timestamp with wall-clock emission time. Motion's
own clock reading (simulation seconds when MotionStub is given the
coordinator's `SimulationClock`) stays in `Details["t"]`; use that for
ordering and freshness, never the outer timestamp.

The shared class is loaded by path, like `cv/universal_logging.py`, so this
module works whether `motion_engine` is imported as a package or run with
`motion_engine/` on `sys.path`. Both loaders write through the same
`logging.getLogger("universal_log")`, so CV and Motion share one run file.
"""

from __future__ import annotations

import math
from enum import Enum
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Callable, Dict, Optional

#: Mission state written before the coordinator supplies one (same as CV).
DEFAULT_STATE: str = "IDLE"


@lru_cache(maxsize=1)
def _logger_class():
    path = Path(__file__).resolve().parents[1] / "universal_log" / "Universal_log.py"
    spec = spec_from_file_location("_motion_shared_universal_log", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load shared logger at {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UniversalLog


def log_entry(info: Dict[str, Any]) -> None:
    """Write one `{"State", "Details"}` record through the shared UniversalLog."""
    _logger_class()(info)


class UniversalLogSink:
    """`contracts.LogSink` implementation that writes to UniversalLog.

    `write` defaults to the real shared logger; tests or a coordinator can
    inject any callable that accepts the record dictionary.
    """

    def __init__(
        self,
        write: Callable[[Dict[str, Any]], object] = log_entry,
        *,
        default_state: str = DEFAULT_STATE,
    ) -> None:
        if not isinstance(default_state, str) or not default_state:
            raise ValueError("default_state must be a nonempty mission-state string")
        self._write = write
        self._default_state = default_state

    def log(
        self,
        module: Any,
        event: str,
        *,
        fields: Optional[Dict[str, Any]] = None,
        state: Optional[Any] = None,
        truth: Optional[Dict[str, Any]] = None,
        decision: Optional[str] = None,
        t: Optional[float] = None,
    ) -> Dict[str, Any]:
        state = _jsonable(state)
        record = {
            "State": state if isinstance(state, str) and state else self._default_state,
            "Details": {
                "module": _jsonable(module),
                "event": event,
                "t": _jsonable(t),
                "fields": _jsonable(dict(fields or {})),
                "synthetic_truth": _jsonable(truth),
                "decision": decision,
            },
        }
        self._write(record)
        return record


def _jsonable(value: Any) -> Any:
    """Make a value safe for UniversalLog's plain `json.dumps` call.

    Enums become their values, objects with `to_dict()` are expanded, and
    non-finite floats become strings ("nan", "inf") so the line stays valid
    JSON. Anything else unknown is written as `str(value)` rather than
    raising inside the logger and stopping the mission loop.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if isinstance(value, dict):
        return {str(_jsonable(k)): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _jsonable(to_dict())
    return str(value)
