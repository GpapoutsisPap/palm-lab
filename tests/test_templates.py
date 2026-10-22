"""Tests for the starter templates offered in the editor."""

import pytest

from palm_lab.actions.models import bindings_from_data
from palm_lab.templates import CATEGORIES, TEMPLATES, Template


@pytest.mark.parametrize("template", TEMPLATES, ids=[t["name"] for t in TEMPLATES])
def test_every_template_is_a_valid_binding(template: Template) -> None:
    """A template must save like any binding, or picking it would leave a broken gesture."""
    (binding,) = bindings_from_data(
        {"binding": [{"gesture": "peace", "name": template["name"], "action": template["action"]}]}
    )
    assert len(binding.actions) == len(template["action"])


def test_templates_have_unique_names_known_categories_and_a_description() -> None:
    names = [t["name"] for t in TEMPLATES]
    assert len(names) == len(set(names))
    assert {t["category"] for t in TEMPLATES} == set(CATEGORIES)
    assert all(t["description"].endswith(".") for t in TEMPLATES)


def test_the_gallery_stays_small() -> None:
    """Research and app galleries suggest roughly 8 to 12 to start with."""
    assert 8 <= len(TEMPLATES) <= 12
