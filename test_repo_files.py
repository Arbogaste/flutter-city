import repo_files


def test_is_dart_source_accepts_plain_dart_file():
    assert repo_files.is_dart_source("lib/src/widget.dart")


def test_is_dart_source_rejects_non_dart():
    assert not repo_files.is_dart_source("README.md")


def test_is_dart_source_rejects_test_files():
    assert not repo_files.is_dart_source("test/widget_test.dart")
    assert not repo_files.is_dart_source("integration_test/app_test.dart")


def test_is_dart_source_rejects_generated_files():
    assert not repo_files.is_dart_source("lib/src/model.g.dart")
    assert not repo_files.is_dart_source("lib/src/model.freezed.dart")
    assert not repo_files.is_dart_source("lib/src/model.mocks.dart")
    assert not repo_files.is_dart_source("lib/src/router.gr.dart")


def test_is_dart_source_rejects_file_under_test_dir_anywhere():
    assert not repo_files.is_dart_source("lib/test/foo.dart")
