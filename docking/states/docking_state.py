from enum import Enum


class DockingState(str, Enum):
    IDLE = "idle"
    APPROACH = "approach"
    SEARCH = "search"
    ALIGN = "align"
    DESCEND = "descend"
    COMPLETE = "complete"
    ABORT = "abort"
