"""The ``get_scale`` tool: where Claude's question meets the music theory.

The scene, from Claude's request to its answer:
    1. Claude calls ``get_scale(root="D", scale="minor")``.
    2. :func:`get_scale` hands the words to :func:`fl_mcp.theory.build_scale`.
    3. If the request makes no musical sense, the theory error becomes a
       :class:`ToolError`, so Claude reads why and can try again.
    4. Otherwise the scale comes back two ways at once: a short sentence for
       Claude to read (:func:`summarize`) and structured data that matches
       :class:`ScaleResult`, for clients that work with data.

This module only translates. It holds no music knowledge of its own.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field

from fl_mcp.theory import DEFAULT_OCTAVE, MusicTheoryError, Scale, build_scale, describe_scale_names

#: The tool's name, as Claude calls it.
TOOL_NAME = "get_scale"

#: A short human title for client UIs.
TOOL_TITLE = "Get scale notes"

#: The description is a prompt: it tells Claude *when* to use the tool, and *why* it beats
#: memory. In the first Claude Desktop test, Claude answered from memory in standard octave
#: naming (C4 = MIDI 60), which doesn't match what FL Studio shows (C5 = 60), so FL's naming
#: comes first as the reason to call the tool.
TOOL_DESCRIPTION = f"""\
Get the notes of a musical scale, correctly spelled, with MIDI note numbers in FL Studio's
octave naming.

Use this whenever the user asks which notes are in a key or scale (for example "what notes
are in D minor?"), and whenever you need exact notes to write a melody, chords or a bass
line. Use it instead of answering from memory, for two reasons:
- Octave names differ between programs. FL Studio calls MIDI 60 "C5"; most references, and
  most of what you remember, call it C4. This tool always matches FL Studio (D5 = 62).
- It always spells notes correctly: D minor contains Bb, never A#; F# major contains E#.

Returns the note names, scale degrees compared with the major scale (1, b3, #4 ...),
semitones above the root, and MIDI note numbers for one octave rising from the root.

Supported scales: {describe_scale_names()}."""

#: Hints for clients: the tool only reads, always gives the same answer, and stays local.
TOOL_ANNOTATIONS = ToolAnnotations(
    title=TOOL_TITLE,
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


class ScaleResult(BaseModel):
    """The structured answer Claude receives, also published as the tool's output schema.

    Cast:
        name: The scale as a person would say it, e.g. "D natural minor".
        root: The root note, e.g. "D".
        scale: The canonical scale name, e.g. "natural_minor".
        notes: Each note, correctly spelled, starting from the root.
        degrees: Each note's degree compared with the major scale.
        intervals: Semitones above the root for each note.
        octave: The FL Studio octave the MIDI numbers start in.
        midi_notes: MIDI note numbers for the notes, rising from the root.
    """

    name: str = Field(description='The scale as a person would say it, e.g. "D natural minor".')
    root: str = Field(description='The root note, e.g. "D".')
    scale: str = Field(description='The canonical scale name, e.g. "natural_minor".')
    notes: list[str] = Field(
        description='Each note, correctly spelled, starting from the root, e.g. "Bb".'
    )
    degrees: list[str] = Field(
        description='Each note\'s degree compared with the major scale, e.g. "b3".'
    )
    intervals: list[int] = Field(description="Semitones above the root for each note.")
    octave: int = Field(description="FL Studio octave of the root (C5 = MIDI 60).")
    midi_notes: list[int] = Field(
        description="MIDI note numbers for the notes, rising from the root."
    )

    @classmethod
    def from_scale(cls, scale: Scale) -> ScaleResult:
        """Translate a theory :class:`Scale` into the shape the tool publishes."""
        return cls(
            name=scale.title,
            root=str(scale.root),
            scale=scale.scale_type.name,
            notes=[str(note) for note in scale.notes],
            degrees=list(scale.degrees),
            intervals=list(scale.intervals),
            octave=scale.octave,
            midi_notes=list(scale.midi_numbers),
        )


def summarize(result: ScaleResult) -> str:
    """Write the short, human-readable answer Claude reads first."""
    return (
        f"{result.name}: {' '.join(result.notes)}\n"
        f"Degrees: {' '.join(result.degrees)}\n"
        f"MIDI from {result.root}{result.octave} (FL naming, C5 = 60): "
        f"{' '.join(map(str, result.midi_notes))}"
    )


def get_scale(
    root: Annotated[
        str,
        Field(
            description=(
                "The note the scale starts on: a letter A-G, optionally with one '#' or 'b'."
            ),
            examples=["D", "F#", "Bb"],
        ),
    ],
    scale: Annotated[
        str,
        Field(
            description="The scale name or an alias. Spaces, hyphens and letter case don't matter.",
            examples=["major", "minor", "harmonic_minor", "minor pentatonic"],
        ),
    ] = "major",
    octave: Annotated[
        int,
        Field(
            description=(
                "FL Studio octave for the MIDI numbers (C5 = MIDI 60). "
                "5 is the middle of the keyboard."
            ),
            ge=0,
            le=10,
        ),
    ] = DEFAULT_OCTAVE,
) -> Annotated[CallToolResult, ScaleResult]:
    """Answer one ``get_scale`` call: build the scale, then reply in words and in data."""
    try:
        scale_built = build_scale(root, scale, octave)  # the theory does the real work
    except MusicTheoryError as error:
        raise ToolError(str(error)) from error  # Claude reads this message and can correct itself

    result = ScaleResult.from_scale(scale_built)  # the structured answer
    return CallToolResult(
        content=[TextContent(type="text", text=summarize(result))],
        structured_content=result.model_dump(mode="json"),
    )


def register(server: MCPServer) -> None:
    """Put ``get_scale`` on the server, with its name, description and hints."""
    server.add_tool(
        get_scale,
        name=TOOL_NAME,
        title=TOOL_TITLE,
        description=TOOL_DESCRIPTION,
        annotations=TOOL_ANNOTATIONS,
    )
