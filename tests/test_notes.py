"""Notes: reading, spelling and placing single notes."""

import pytest

from fl_mcp.theory import NoteName, OutOfMidiRangeError, UnknownNoteError
from fl_mcp.theory.notes import spell_with_letter


@pytest.mark.parametrize(
    ("text", "letter", "accidental"),
    [
        ("D", "D", 0),
        ("f#", "F", 1),
        ("Bb", "B", -1),
        ("bb", "B", -1),  # lower-case "b" letter, then a flat
        ("B♭", "B", -1),
        ("C♯", "C", 1),
        ("C##", "C", 2),
        ("Ebb", "E", -2),
        ("  G  ", "G", 0),
    ],
)
def test_parse_reads_letters_and_accidentals(text: str, letter: str, accidental: int) -> None:
    assert NoteName.parse(text) == NoteName(letter, accidental)


@pytest.mark.parametrize("text", ["", "   ", "H", "C#b", "X#", "D minor", "BB", "C###"])
def test_parse_rejects_what_it_cannot_read(text: str) -> None:
    with pytest.raises(UnknownNoteError):
        NoteName.parse(text)


def test_parse_error_explains_how_to_write_a_note() -> None:
    with pytest.raises(UnknownNoteError, match="letter A-G"):
        NoteName.parse("H")


@pytest.mark.parametrize(("letter", "accidental"), [("H", 0), ("C", 3), ("C", -3)])
def test_impossible_notes_cannot_be_created(letter: str, accidental: int) -> None:
    with pytest.raises(UnknownNoteError):
        NoteName(letter, accidental)


@pytest.mark.parametrize(
    ("note", "pitch_class"),
    [(NoteName("C"), 0), (NoteName("B", 1), 0), (NoteName("C", -1), 11), (NoteName("B", -1), 10)],
)
def test_pitch_class_wraps_around_the_octave(note: NoteName, pitch_class: int) -> None:
    assert note.pitch_class == pitch_class


@pytest.mark.parametrize(
    ("note", "octave", "midi"),
    [
        (NoteName("C"), 5, 60),  # FL Studio's middle C
        (NoteName("D"), 5, 62),
        (NoteName("B", 1), 4, 60),  # B#4 is the same key as C5
        (NoteName("C", -1), 5, 59),  # Cb5 is the same key as B4
        (NoteName("C"), 0, 0),
        (NoteName("G"), 10, 127),
    ],
)
def test_midi_number_uses_fl_octave_naming(note: NoteName, octave: int, midi: int) -> None:
    assert note.midi_number(octave) == midi


@pytest.mark.parametrize(("note", "octave"), [(NoteName("G", 1), 10), (NoteName("C"), -1)])
def test_midi_number_refuses_keys_off_the_keyboard(note: NoteName, octave: int) -> None:
    with pytest.raises(OutOfMidiRangeError):
        note.midi_number(octave)


@pytest.mark.parametrize(
    ("note", "text"),
    [
        (NoteName("B", -1), "Bb"),
        (NoteName("F", 1), "F#"),
        (NoteName("C", -2), "Cbb"),
        (NoteName("E"), "E"),
    ],
)
def test_str_spells_in_ascii(note: NoteName, text: str) -> None:
    assert str(note) == text


@pytest.mark.parametrize(
    ("letter", "pitch_class", "expected"), [("B", 10, "Bb"), ("A", 10, "A#"), ("E", 5, "E#")]
)
def test_spell_with_letter_picks_the_right_accidental(
    letter: str, pitch_class: int, expected: str
) -> None:
    assert str(spell_with_letter(letter, pitch_class)) == expected
