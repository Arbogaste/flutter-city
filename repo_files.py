#!/usr/bin/env python3
# Adapted from code-city (https://github.com/victorrentea/code-city), Unlicense.
"""Which files are IN the repo under analysis — asked of git, not of the filesystem.

Same reasoning as upstream: `git ls-files` is the repo's own definition of what
belongs to it (every generated/vendored/scratch dir is already in a .gitignore
somebody keeps current), so a stray file from an agent worktree or IDE metadata
directory never sneaks into the city.
"""
from __future__ import annotations

import os
import subprocess
import sys

_CACHE: dict[str, list[str]] = {}

_GENERATED_SUFFIXES = (".g.dart", ".freezed.dart", ".mocks.dart", ".gr.dart")


def is_dart_source(rel: str) -> bool:
    """The pipeline's one inclusion rule: non-test .dart, not generated.

    Generated files (`*.g.dart`, `*.freezed.dart`, `*.mocks.dart`, `*.gr.dart`)
    are checked-in build output from build_runner/freezed/mockito/auto_route —
    nobody wrote them by hand, the same reasoning code-city applies to
    `package-info.java`.
    """
    if not rel.endswith(".dart"):
        return False
    if any(rel.endswith(suffix) for suffix in _GENERATED_SUFFIXES):
        return False
    segs = rel.split("/")
    return not any(seg in ("test", "integration_test") for seg in segs[:-1])


def prune_set() -> set[str]:
    """The extra directory names HEATMAP_PRUNE asks to drop on top of git's answer."""
    return {d for d in os.environ.get("HEATMAP_PRUNE", "").split(",") if d}


def _is_pruned(rel: str, prune: set[str]) -> bool:
    return any(seg in prune for seg in rel.split("/")[:-1])


def tracked_paths(repo: str) -> list[str]:
    """Every file the repo claims, repo-relative and slash-separated, sorted."""
    repo = os.path.abspath(repo)
    if repo in _CACHE:
        return _CACHE[repo]
    proc = subprocess.run(
        ["git", "-C", repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        sys.exit(f"{repo} is not a git checkout, and the city is built from what git "
                 f"says the repo contains: {err or 'git ls-files failed'}")
    names = proc.stdout.decode("utf-8", "surrogateescape").split("\0")
    prune = prune_set()
    paths = sorted({n for n in names if n and not _is_pruned(n, prune)})
    paths = [p for p in paths if os.path.isfile(os.path.join(repo, p))]
    _CACHE[repo] = paths
    return paths


def dart_sources(repo: str) -> list[str]:
    """Absolute paths of the Dart sources the city is made of."""
    repo = os.path.abspath(repo)
    return [os.path.join(repo, rel) for rel in tracked_paths(repo) if is_dart_source(rel)]
