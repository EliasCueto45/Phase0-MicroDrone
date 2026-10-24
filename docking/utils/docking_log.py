"""JSON-lines event output for synthetic docking runs."""

from dataclasses import asdict
import json
from typing import TextIO

from docking.alignment import AlignmentResult
from docking.states import DockingInput, DockingUpdate


def write_docking_event(
    stream: TextIO,
    inputs: DockingInput,
    update: DockingUpdate,
    alignment: AlignmentResult,
    origin_id: str,
) -> None:
    event = {
        "synthetic": True,
        "frame": "local_enu",
        "clock": "simulation",
        "schema_version": 1,
        "origin_id": origin_id,
        "inputs": asdict(inputs),
        "alignment": asdict(alignment),
        "update": update.to_dict(),
    }
    stream.write(json.dumps(event, allow_nan=False) + "\n")
