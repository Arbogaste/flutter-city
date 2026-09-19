import textwrap
from compute_crap import parse_lcov


def test_parse_lcov_basic():
    lcov = textwrap.dedent("""\
        SF:lib/src/a.dart
        DA:1,1
        DA:2,0
        DA:3,1
        end_of_record
        SF:lib/src/b.dart
        DA:1,5
        end_of_record
    """)
    result = parse_lcov(lcov)
    assert result["lib/src/a.dart"] == (2, 3)
    assert result["lib/src/b.dart"] == (1, 1)


def test_parse_lcov_empty_is_empty_dict():
    assert parse_lcov("") == {}
