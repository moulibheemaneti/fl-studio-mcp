"""The get_scale tool, tested through the real MCP protocol (in-process client)."""

import pytest
from mcp import Client

from fl_mcp.server import build_server
from fl_mcp.theory import SCALE_TYPES

pytestmark = pytest.mark.anyio


async def call_get_scale(**arguments: object):
    """Call get_scale on a fresh server, the way an MCP client would."""
    async with Client(build_server()) as client:
        return await client.call_tool("get_scale", arguments)


async def test_server_lists_get_scale_with_schemas_and_hints() -> None:
    async with Client(build_server()) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    tool = tools["get_scale"]
    assert tool.input_schema["required"] == ["root"]
    assert set(tool.input_schema["properties"]) == {"root", "scale", "octave"}
    assert set(tool.output_schema["properties"]) >= {"notes", "degrees", "midi_notes"}
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False


async def test_description_tells_claude_when_to_use_it_and_lists_every_scale() -> None:
    async with Client(build_server()) as client:
        (tool,) = (await client.list_tools()).tools

    assert "Use this whenever" in tool.description
    assert "instead of answering from memory" in tool.description
    assert '"C5"' in tool.description  # the octave naming Claude gets wrong from memory
    for scale_type in SCALE_TYPES:
        assert scale_type.name in tool.description


async def test_server_instructions_point_claude_to_get_scale() -> None:
    async with Client(build_server()) as client:
        instructions = client.instructions

    assert "get_scale" in instructions
    assert "C5" in instructions


async def test_d_minor_answers_in_words_and_in_data() -> None:
    result = await call_get_scale(root="D", scale="minor")

    assert result.is_error is False
    assert "D natural minor: D E F G A Bb C" in result.content[0].text
    assert result.structured_content == {
        "name": "D natural minor",
        "root": "D",
        "scale": "natural_minor",
        "notes": ["D", "E", "F", "G", "A", "Bb", "C"],
        "degrees": ["1", "2", "b3", "4", "5", "b6", "b7"],
        "intervals": [0, 2, 3, 5, 7, 8, 10],
        "octave": 5,
        "midi_notes": [62, 64, 65, 67, 69, 70, 72],
    }


async def test_scale_and_octave_are_optional() -> None:
    result = await call_get_scale(root="C")

    assert result.structured_content["scale"] == "major"
    assert result.structured_content["midi_notes"][0] == 60


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"root": "H"}, "letter A-G"),
        ({"root": "C", "scale": "sad"}, "natural_minor"),  # lists the supported scales
        ({"root": "C##"}, "more than one sharp or flat"),
        ({"root": "C", "octave": 10}, "outside 0-127"),
        ({"root": "C", "octave": 42}, "less than or equal to 10"),
    ],
)
async def test_bad_requests_come_back_as_errors_claude_can_read(
    arguments: dict, message: str
) -> None:
    result = await call_get_scale(**arguments)

    assert result.is_error is True
    assert message in result.content[0].text
