"""Bridge the shared logger's current filename to the CV module.

Load by path because ``universal _log/Universal_log.py`` is not a conventional
Python import name. Keep its implementation and output policy in one place.
"""

from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


@lru_cache(maxsize=1)
def _logger_class():
    path = Path(__file__).resolve().parents[1] / "universal _log" / "Universal_log.py"
    spec = spec_from_file_location("_cv_shared_universal_log", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load shared logger at {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UniversalLog


def log_entry(info: dict) -> None:
    """Write through the repository's UniversalLog class."""
    _logger_class()(info)
