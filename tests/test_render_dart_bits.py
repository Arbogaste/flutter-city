import subprocess
import sys
import os
from pathlib import Path

FIXTURE_TSV = (
    "path\tbytes\tlines\tcommits\tbug_commits\tcommits_per_kloc\tbugs_per_kloc"
    "\tbugs_per_commit\tcognitive_complexity\tcomplexity_per_kloc\tfan_in\tfan_out"
    "\tcommitters\tcochange_out\tcoverage\tcoverage_acceptance\tcrap_max"
    "\tcrap_max_method\tcrap_load\tcrap_per_kloc\tcrappy_methods\n"
    "lib/src/my_widget.dart\t500\t40\t3\t0\t0.1\t0.0\t0.0\t2\t0.05\t1\t2\t1\t0.0"
    "\t\t\t0.0\t\t0.0\t0.0\t0\n"
)


def test_render_codecity_strips_dart_extension(tmp_path):
    (tmp_path / "codemap.tsv").write_text(FIXTURE_TSV)
    env = dict(os.environ, HEATMAP_OUT=str(tmp_path), HEATMAP_REPO=str(tmp_path))
    here = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, str(here / "render_codecity.py"), str(tmp_path / "codemap.tsv")],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    html = (tmp_path / "codecity.html").read_text()
    assert "my_widget" in html
    assert "package-info" not in html
    assert "my_widget.dart.dart" not in html
