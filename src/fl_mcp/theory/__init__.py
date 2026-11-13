"""Music theory: the facts every composition is built from.

This layer knows nothing about MCP or FL Studio. It answers questions like
"which notes are in D minor?" with plain Python values, so it can be tested on
its own and reused by any tool.

Cast:
    notes:  :class:`NoteName`, a correctly spelled note and its pitch.
    scales: :class:`ScaleType` recipes and :func:`build_scale`.
    errors: :class:`MusicTheoryError` and its children, raised for impossible requests.
"""

from fl_mcp.theory.errors import (
    MusicTheoryError,
    OutOfMidiRangeError,
    UnknownNoteError,
    UnknownScaleError,
)
from fl_mcp.theory.notes import NoteName
from fl_mcp.theory.scales import (
    DEFAULT_OCTAVE,
    SCALE_TYPES,
    Scale,
    ScaleType,
    build_scale,
    describe_scale_names,
    find_scale_type,
)

__all__ = [
    "DEFAULT_OCTAVE",
    "SCALE_TYPES",
    "MusicTheoryError",
    "NoteName",
    "OutOfMidiRangeError",
    "Scale",
    "ScaleType",
    "UnknownNoteError",
    "UnknownScaleError",
    "build_scale",
    "describe_scale_names",
    "find_scale_type",
]
