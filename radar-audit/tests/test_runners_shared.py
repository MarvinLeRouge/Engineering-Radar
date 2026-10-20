from pathlib import Path

from radar_audit.runners.shared import relativize_file_field, relativize_path_keys


def test_relativize_file_field_converts_an_absolute_path_under_target_path():
    target_path = Path("/repo")
    items = [{"file": "/repo/src/a.py", "line": 1}]

    relativize_file_field(items, target_path)

    assert items[0]["file"] == "src/a.py"


def test_relativize_file_field_leaves_an_already_relative_path_unchanged():
    target_path = Path("/repo")
    items = [{"file": "src/a.py", "line": 1}]

    relativize_file_field(items, target_path)

    assert items[0]["file"] == "src/a.py"


def test_relativize_file_field_leaves_a_path_outside_target_path_unchanged():
    target_path = Path("/repo")
    items = [{"file": "/elsewhere/a.py", "line": 1}]

    relativize_file_field(items, target_path)

    assert items[0]["file"] == "/elsewhere/a.py"


def test_relativize_file_field_skips_items_with_no_file_key():
    target_path = Path("/repo")
    items = [{"line": 1}]

    relativize_file_field(items, target_path)

    assert items == [{"line": 1}]


def test_relativize_file_field_skips_a_none_file_value():
    target_path = Path("/repo")
    items = [{"file": None, "line": 1}]

    relativize_file_field(items, target_path)

    assert items[0]["file"] is None


def test_relativize_file_field_uses_a_custom_key():
    target_path = Path("/repo")
    items = [{"path": "/repo/src/a.py"}]

    relativize_file_field(items, target_path, key="path")

    assert items[0]["path"] == "src/a.py"


def test_relativize_path_keys_converts_absolute_keys_to_relative():
    target_path = Path("/repo")
    mapping = {"/repo/src/a.py": {"sloc": 10}}

    result = relativize_path_keys(mapping, target_path)

    assert result == {"src/a.py": {"sloc": 10}}


def test_relativize_path_keys_leaves_an_already_relative_key_unchanged():
    target_path = Path("/repo")
    mapping = {"src/a.py": {"sloc": 10}}

    result = relativize_path_keys(mapping, target_path)

    assert result == {"src/a.py": {"sloc": 10}}
