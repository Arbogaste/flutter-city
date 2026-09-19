#!/usr/bin/env python3
# Adapted from code-city (https://github.com/victorrentea/code-city), Unlicense.
"""Compute fan-in and fan-out per non-test/non-generated Dart file.

Unlike Java, a Dart `import` names a FILE directly (`package:pkg/src/x.dart` or
a relative path), not a class — so resolution here is a path computation, no
class-FQN map needed (code-city's compute_fanio.py builds one from
complexity-per-class.tsv only because Java imports name classes).

Output: fanio-per-file.tsv (file, fan_in, fan_out), coupling-edges.tsv
(source, target, weight, line) — same shape as code-city's.
"""
from __future__ import annotations

import bisect
import os
import re
import sys
from collections import Counter, defaultdict
import subprocess

import repo_files

_here = os.path.dirname(os.path.abspath(__file__))


def _git_root(start):
    try:
        return subprocess.check_output(
            ["git", "-C", start, "rev-parse", "--show-toplevel"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return start


REPO = os.path.abspath(os.environ.get("HEATMAP_REPO") or _git_root(_here))
OUT_DIR = os.path.abspath(os.environ.get("HEATMAP_OUT") or REPO)
OUT = os.path.join(OUT_DIR, "fanio-per-file.tsv")
EDGES_OUT = os.path.join(OUT_DIR, "coupling-edges.tsv")

IMPORT_RE = re.compile(r"""^\s*(?:import|export)\s+['"]([^'"]+)['"]""", re.MULTILINE)


def strip_comments_and_strings(src: str) -> str:
    """Dart source with comments and string literals blanked (newlines kept).

    This is only used to keep the regex scan honest against a `'y.dart'`
    mentioned inside a comment or an unrelated string; the actual import/export
    declarations are read straight off the untouched source by IMPORT_RE,
    which anchors on the `import`/`export` keyword itself.
    """
    out = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif ch == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(c if c == "\n" else " " for c in src[i:j]))
            i = j
        elif src.startswith("'''", i) or src.startswith('"""', i):
            quote = src[i:i + 3]
            j = src.find(quote, i + 3)
            j = n if j < 0 else j + 3
            out.append("".join(c if c == "\n" else " " for c in src[i:j]))
            i = j
        elif ch in "\"'":
            j = i + 1
            while j < n and src[j] != ch:
                j += 2 if src[j] == "\\" else 1
            j = min(j + 1, n)
            out.append("".join(c if c == "\n" else " " for c in src[i:j]))
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def resolve_import(from_rel: str, uri: str, pkg_name: str) -> "str | None":
    """Repo-relative target path for an import URI seen in `from_rel`, or None
    if it points outside the repo (SDK, another package's own pub dependency)."""
    if uri.startswith("dart:"):
        return None
    if uri.startswith("package:"):
        rest = uri[len("package:"):]
        pkg, _, path = rest.partition("/")
        if pkg != pkg_name or not path:
            return None
        return f"lib/{path}"
    if uri.startswith(("http:", "https:")):
        return None
    base_dir = from_rel.rsplit("/", 1)[0] if "/" in from_rel else ""
    parts = (base_dir.split("/") if base_dir else []) + uri.split("/")
    resolved: list[str] = []
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            if resolved:
                resolved.pop()
            continue
        resolved.append(part)
    return "/".join(resolved)


def read_package_name(repo: str) -> str:
    pubspec = os.path.join(repo, "pubspec.yaml")
    try:
        with open(pubspec, encoding="utf-8") as f:
            for line in f:
                if line.startswith("name:"):
                    return line.split(":", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return ""


def main():
    pkg_name = read_package_name(REPO)
    dart_files = repo_files.dart_sources(REPO)
    known = set(os.path.relpath(p, REPO) for p in dart_files)
    print(f"scanning {len(dart_files)} dart files (package: {pkg_name!r})", file=sys.stderr)

    fan_out = defaultdict(dict)
    fan_sites = defaultdict(dict)

    for ap in dart_files:
        rel = os.path.relpath(ap, REPO)
        try:
            with open(ap, encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            continue

        line_starts = [0]
        for i, ch in enumerate(raw):
            if ch == "\n":
                line_starts.append(i + 1)

        def line_of(offset):
            return bisect.bisect_right(line_starts, offset)

        targets: Counter = Counter()
        sites: dict[str, int] = {}
        for m in IMPORT_RE.finditer(raw):
            uri = m.group(1)
            target = resolve_import(rel, uri, pkg_name)
            if target is None or target == rel or target not in known:
                continue
            targets[target] += 1
            line = line_of(m.start())
            if target not in sites or line < sites[target]:
                sites[target] = line

        fan_out[rel] = dict(targets)
        fan_sites[rel] = sites

    fan_in = defaultdict(int)
    for src_file, tgts in fan_out.items():
        for tf in tgts:
            fan_in[tf] += 1

    rows = []
    all_files = set(os.path.relpath(p, REPO) for p in dart_files)
    for f in all_files:
        rows.append((f, fan_in.get(f, 0), len(fan_out.get(f, {}))))
    rows.sort()

    with open(OUT, "w") as f:
        f.write("file\tfan_in\tfan_out\n")
        for r in rows:
            f.write(f"{r[0]}\t{r[1]}\t{r[2]}\n")
    print(f"wrote {len(rows)} rows to {OUT}", file=sys.stderr)

    edges = 0
    with open(EDGES_OUT, "w") as f:
        f.write("source\ttarget\tweight\tline\n")
        for src_file in sorted(fan_out):
            sites = fan_sites.get(src_file, {})
            for tf in sorted(fan_out[src_file]):
                f.write(f"{src_file}\t{tf}\t{fan_out[src_file][tf]}\t{sites.get(tf, 0)}\n")
                edges += 1
    print(f"wrote {edges} edges to {EDGES_OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
