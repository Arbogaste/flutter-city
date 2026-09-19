from compute_fanio import resolve_import, strip_comments_and_strings


def test_resolve_relative_import():
    assert resolve_import("lib/src/a.dart", "b.dart", "my_pkg") == "lib/src/b.dart"
    assert resolve_import("lib/src/a.dart", "../b.dart", "my_pkg") == "lib/b.dart"


def test_resolve_package_import_same_package():
    assert resolve_import("lib/src/a.dart", "package:my_pkg/src/b.dart", "my_pkg") == "lib/src/b.dart"


def test_resolve_package_import_other_package_is_none():
    assert resolve_import("lib/a.dart", "package:http/http.dart", "my_pkg") is None


def test_resolve_dart_sdk_import_is_none():
    assert resolve_import("lib/a.dart", "dart:async", "my_pkg") is None


def test_strip_comments_and_strings_keeps_line_count():
    src = "// c\nimport 'x.dart';\n/* block\ncomment */\nvar s = \"has import 'y.dart' inside\";\n"
    stripped = strip_comments_and_strings(src)
    assert stripped.count("\n") == src.count("\n")
    assert "import" not in stripped.split("\n")[0]
    assert "y.dart" not in stripped
