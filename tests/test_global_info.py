import json

import pytest

from allure_magic import GlobalInfoItem, load_global_info, write_global_info


def test_roundtrip(tmp_path):
    items = [GlobalInfoItem("a", "1"), GlobalInfoItem("L", "https://x.io", "X", "link")]
    path = write_global_info(items, tmp_path)
    assert path.name == "global-info.json"
    assert load_global_info(path) == items


def test_none_fields_are_omitted(tmp_path):
    path = write_global_info([GlobalInfoItem("only name")], tmp_path)
    assert json.loads(path.read_text()) == [{"name": "only name", "decoration": "text"}]


@pytest.mark.parametrize("kwargs", [{"name": ""}, {"name": "x", "decoration": "bold"}, {"name": "x", "decoration": "link"}])
def test_validation(kwargs):
    with pytest.raises(ValueError):
        GlobalInfoItem(**kwargs)


def test_missing_file_is_empty(tmp_path):
    assert load_global_info(tmp_path / "nope.json") == []


def test_fixtures_are_valid():
    for p in ("allure-results/global-info.json", "global-info/src/dist/static/global-info.json"):
        for item in load_global_info(p):
            assert item.name
