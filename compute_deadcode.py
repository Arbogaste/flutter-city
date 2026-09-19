#!/usr/bin/env python3
"""Optional dead-code density per file, via the `dead_code_analyzer` Dart CLI
(https://pub.dev/packages/dead_code_analyzer) if it's on PATH.

Off by default in the sense that matters: a checkout with no Dart SDK / no
`dead_code_analyzer` installed still builds a complete city, just without this
one metric — same degrade-gracefully pattern as compute_crap.py.

Output: OUT_DIR/deadcode-per-file.tsv (file, unused_count), written only if the
tool ran. `dead_code_analyzer`'s own regex-based analysis is a known source of
false positives on constructors (see its README's Limitations section) — treat
this metric as a rough density signal, not a precise count.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

_here = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath(os.environ.get("HEATMAP_REPO") or _here)
OUT_DIR = os.path.abspath(os.environ.get("HEATMAP_OUT") or REPO_DIR)
os.makedirs(OUT_DIR, exist_ok=True)
OUT_FILE = os.path.join(OUT_DIR, "deadcode-per-file.tsv")

REPORT_LINE_RE = re.compile(r"in\s+(\S+\.dart):\d+")


def tool_available() -> bool:
    return shutil.which("dead_code_analyzer") is not None


def parse_report(text: str) -> dict:
    counts: dict = {}
    for line in text.splitlines():
        m = REPORT_LINE_RE.search(line)
        if m:
            path = m.group(1)
            counts[path] = counts.get(path, 0) + 1
    return counts


def main():
    if not tool_available():
        print("dead_code_analyzer not on PATH (dart pub global activate dead_code_analyzer); "
              "dead-code metric will be absent from this city", file=sys.stderr)
        if os.path.exists(OUT_FILE):
            os.remove(OUT_FILE)
        return

    with tempfile.TemporaryDirectory() as tmp:
        try:
            proc = subprocess.run(
                ["dead_code_analyzer", "-p", REPO_DIR, "-o", tmp, "--funcs", "-q"],
                capture_output=True, text=True, timeout=300,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            print(f"dead_code_analyzer failed to run: {e}", file=sys.stderr)
            return
        counts = parse_report(proc.stdout)

    if not counts:
        print("dead_code_analyzer found nothing to report", file=sys.stderr)
        if os.path.exists(OUT_FILE):
            os.remove(OUT_FILE)
        return

    with open(OUT_FILE, "w") as f:
        f.write("file\tunused_count\n")
        for rel, n in sorted(counts.items()):
            f.write(f"{rel}\t{n}\n")
    print(f"wrote {len(counts)} rows to {OUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
