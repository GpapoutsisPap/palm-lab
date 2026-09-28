"""Tests for parsing the TOML bindings format."""

import re

import pytest

from palm_lab.actions.errors import InvalidBindingError
from palm_lab.actions.models import (
    DEFAULT_STEP_DELAY_SECONDS,
    ActionType,
    load_bindings,
    parse_bindings,
)

MINIMAL = """
[[binding]]
gesture = "peace"
name = "Test"
  [[binding.action]]
  type = "launch"
  target = "spotify"
"""


def test_parses_a_minimal_binding() -> None:
    """One binding with one action round-trips into the data model."""
    (binding,) = parse_bindings(MINIMAL)
    assert binding.gesture == "peace"
    assert binding.name == "Test"
    assert len(binding.actions) == 1
    assert binding.actions[0].type is ActionType.LAUNCH
    assert binding.actions[0].target == "spotify"


def test_actions_keep_their_declared_order() -> None:
    """Actions run top to bottom, so the parser must not reorder them."""
    text = """
    [[binding]]
    gesture = "peace"
    name = "Three steps"
      [[binding.action]]
      type = "launch"
      target = "first"
      [[binding.action]]
      type = "open_url"
      target = "https://second.example"
      [[binding.action]]
      type = "launch"
      target = "third"
    """
    (binding,) = parse_bindings(text)
    assert [a.target for a in binding.actions] == [
        "first",
        "https://second.example",
        "third",
    ]


def test_step_delay_defaults_when_absent() -> None:
    """A binding that omits the delay gets the shared default."""
    (binding,) = parse_bindings(MINIMAL)
    assert binding.step_delay_seconds == DEFAULT_STEP_DELAY_SECONDS


def test_step_delay_accepts_an_integer() -> None:
    """TOML distinguishes 1 from 1.0; both are valid delays."""
    text = """
[[binding]]
gesture = "peace"
name = "Test"
step_delay_seconds = 1
  [[binding.action]]
  type = "launch"
  target = "spotify"
"""
    (binding,) = parse_bindings(text)
    assert binding.step_delay_seconds == 1.0
    assert isinstance(binding.step_delay_seconds, float)


def test_bindings_are_immutable() -> None:
    """Configuration is read once at startup and must not be mutated."""
    (binding,) = parse_bindings(MINIMAL)
    with pytest.raises(AttributeError):
        binding.gesture = "fist"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("[[binding]\ngesture=", "not valid TOML", id="malformed-toml"),
        pytest.param("other = 1", "[[binding]] sections", id="no-binding-section"),
        pytest.param("binding = 5", "[[binding]] sections", id="binding-not-a-list"),
        pytest.param(
            '[[binding]]\ngesture=""\nname="n"\n[[binding.action]]\ntype="launch"\ntarget="x"',
            "'gesture' must be a non-empty string",
            id="empty-gesture",
        ),
        pytest.param(
            '[[binding]]\nname="n"\n[[binding.action]]\ntype="launch"\ntarget="x"',
            "'gesture' must be a non-empty string",
            id="missing-gesture",
        ),
        pytest.param(
            '[[binding]]\ngesture="g"\n[[binding.action]]\ntype="launch"\ntarget="x"',
            "'name' must be a non-empty string",
            id="missing-name",
        ),
        pytest.param(
            '[[binding]]\ngesture="g"\nname="n"',
            "at least one [[binding.action]]",
            id="no-actions",
        ),
        pytest.param(
            '[[binding]]\ngesture="g"\nname="n"\n[[binding.action]]\ntype="lauch"\ntarget="x"',
            "unknown type 'lauch'",
            id="misspelled-type",
        ),
        pytest.param(
            '[[binding]]\ngesture="g"\nname="n"\n[[binding.action]]\ntarget="x"',
            "'type' must be a string",
            id="missing-type",
        ),
        pytest.param(
            '[[binding]]\ngesture="g"\nname="n"\n[[binding.action]]\ntype="launch"',
            "'target' must be a non-empty string",
            id="missing-target",
        ),
        pytest.param(
            '[[binding]]\ngesture="g"\nname="n"\nstep_delay_seconds="soon"\n'
            '[[binding.action]]\ntype="launch"\ntarget="x"',
            "must be a number",
            id="non-numeric-delay",
        ),
        pytest.param(
            '[[binding]]\ngesture="g"\nname="n"\nstep_delay_seconds=-1\n'
            '[[binding.action]]\ntype="launch"\ntarget="x"',
            "cannot be negative",
            id="negative-delay",
        ),
    ],
)
def test_bad_configuration_is_rejected(text: str, expected: str) -> None:
    """Every malformed file raises InvalidBindingError naming the problem."""
    with pytest.raises(InvalidBindingError, match=re.escape(expected)):
        parse_bindings(text)


def test_unknown_type_error_lists_the_valid_options() -> None:
    """A typo should tell the user what they could have written instead."""
    text = '[[binding]]\ngesture="g"\nname="n"\n[[binding.action]]\ntype="lauch"\ntarget="x"'
    with pytest.raises(InvalidBindingError) as caught:
        parse_bindings(text)
    message = str(caught.value)
    for action_type in ActionType:
        assert action_type.value in message


def test_errors_name_the_offending_binding_and_action() -> None:
    """With several bindings, the message must say which one is wrong."""
    text = """
    [[binding]]
    gesture = "peace"
    name = "Fine"
      [[binding.action]]
      type = "launch"
      target = "ok"

    [[binding]]
    gesture = "fist"
    name = "Broken"
      [[binding.action]]
      type = "launch"
      target = "ok"
      [[binding.action]]
      type = "nope"
      target = "x"
    """
    with pytest.raises(InvalidBindingError, match=re.escape("Binding 2, action 2")):
        parse_bindings(text)


def test_load_bindings_reads_a_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """load_bindings parses the file at the given path."""
    path = tmp_path / "bindings.toml"
    path.write_text(MINIMAL, encoding="utf-8")
    (binding,) = load_bindings(path)
    assert binding.gesture == "peace"


def test_load_bindings_reports_a_missing_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A missing file names the path it looked for."""
    missing = tmp_path / "nope.toml"
    with pytest.raises(InvalidBindingError, match=re.escape(missing.name)):
        load_bindings(missing)
