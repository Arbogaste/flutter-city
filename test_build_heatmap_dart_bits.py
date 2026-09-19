import build_heatmap


def test_counts_toward_diagram_uses_dart_rule():
    assert build_heatmap._counts_toward_diagram("lib/src/a.dart")
    assert not build_heatmap._counts_toward_diagram("test/a_test.dart")


def test_build_descriptor_is_pubspec():
    assert build_heatmap._is_build_descriptor("pubspec.yaml")
    assert not build_heatmap._is_build_descriptor("pom.xml")
    assert not build_heatmap._is_build_descriptor("build.gradle")


def test_district_uses_lib_not_java():
    assert build_heatmap._district("lib/src/widgets/foo.dart") == "src.widgets"
    assert build_heatmap._district("bin/main.dart") == "bin"
