from unittest.mock import patch
import compute_deadcode


def test_skips_when_tool_not_on_path():
    with patch("shutil.which", return_value=None):
        assert compute_deadcode.tool_available() is False


def test_parse_report_counts_per_file():
    report = (
        "Unused class 'Foo' in lib/src/a.dart:10\n"
        "Unused function 'bar' in lib/src/a.dart:20\n"
        "Unused class 'Baz' in lib/src/b.dart:5\n"
    )
    counts = compute_deadcode.parse_report(report)
    assert counts == {"lib/src/a.dart": 2, "lib/src/b.dart": 1}


def test_parse_report_empty():
    assert compute_deadcode.parse_report("") == {}
