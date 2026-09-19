#!/usr/bin/env python3
# Adapted from code-city (https://github.com/victorrentea/code-city), Unlicense.
"""Per-file line coverage from a `lcov.info` report (flutter/dart test --coverage).

code-city's Java version computes CRAP (complexity-weighted coverage risk) from
JaCoCo, which emits a per-METHOD complexity counter alongside line coverage.
lcov has no such per-method complexity counter — only per-line hit counts — so
true CRAP cannot be computed from it. This still writes the CRAP columns
code-city's build_heatmap.py/render_codecity.py expect (so those stay
unmodified), just always zero/empty: only cov_covered/cov_total carry real
data here. See docs/superpowers/specs/2026-09-19-flutter-city-design.md.

Output: OUT_DIR/crap-per-file.tsv, written only if an lcov.info was found —
same "absence is not zero" rule as upstream: an unmeasured file gets no row.
"""
import glob
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.abspath(os.environ.get("HEATMAP_REPO") or _here)
OUT_DIR = os.path.abspath(os.environ.get("HEATMAP_OUT") or REPO_DIR)
os.makedirs(OUT_DIR, exist_ok=True)
OUT_FILE = os.path.join(OUT_DIR, "crap-per-file.tsv")

DEFAULT_GLOBS = ["coverage/lcov.info"]


def lcov_paths():
    configured = os.environ.get("CODECITY_LCOV", "")
    patterns = [p for p in configured.replace(",", ":").split(":") if p.strip()]
    if not patterns:
        patterns = DEFAULT_GLOBS
    found = []
    for pat in patterns:
        pat = pat if os.path.isabs(pat) else os.path.join(REPO_DIR, pat)
        found.extend(sorted(glob.glob(pat, recursive=True)))
    return [p for p in found if os.path.isfile(p)]


def parse_lcov(text: str) -> dict:
    """{repo-relative file: (lines_covered, lines_total)}."""
    result: dict = {}
    current = None
    covered = total = 0
    for line in text.splitlines():
        if line.startswith("SF:"):
            current = line[3:].strip()
            covered = total = 0
        elif line.startswith("DA:"):
            _, hits = line[3:].split(",", 1)
            total += 1
            if int(hits) > 0:
                covered += 1
        elif line == "end_of_record":
            if current is not None:
                result[current] = (covered, total)
            current = None
    return result


def _to_repo_relative(path: str) -> str:
    abs_path = path if os.path.isabs(path) else os.path.join(REPO_DIR, path)
    try:
        return os.path.relpath(abs_path, REPO_DIR)
    except ValueError:
        return path


def main():
    paths = lcov_paths()
    if not paths:
        print("no lcov.info found (set CODECITY_LCOV, or run `flutter test --coverage`); "
              "coverage will be absent from this city", file=sys.stderr)
        if os.path.exists(OUT_FILE):
            os.remove(OUT_FILE)
        return

    merged: dict = {}
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as f:
            for rel, (c, t) in parse_lcov(f.read()).items():
                rel = _to_repo_relative(rel)
                pc, pt = merged.get(rel, (0, 0))
                merged[rel] = (pc + c, pt + t)

    rows = sorted(merged.items())
    with open(OUT_FILE, "w") as f:
        f.write("file\tcov_covered\tcov_total\tcrap_max\tcrap_max_method\tcrap_load"
                "\tcrappy_methods\tmethods\tacc_covered\tacc_total\n")
        for rel, (c, t) in rows:
            f.write(f"{rel}\t{c}\t{t}\t0.0\t\t0.0\t0\t0\t0\t0\n")

    covered = sum(c for c, _ in merged.values())
    total = sum(t for _, t in merged.values())
    pct = (100.0 * covered / total) if total else 0.0
    print(f"read {len(paths)} lcov report(s): {len(rows)} files, {pct:.1f}% line coverage "
          f"(CRAP columns are placeholders — lcov has no per-method complexity counter)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
