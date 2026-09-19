#!/usr/bin/env bash
# Build a flutter-city (3D city + 2D codemap) for a folder of Dart/Flutter sources.
#
#   ./generate.sh [REPO] [OUT]
#     REPO   git checkout to analyse   (default: $PWD's git toplevel)
#     OUT    where the artifacts land  (default: REPO/.flutter-city)
#
# Pipeline:
#   compute_complexity.py  -> complexity-per-{class,file}.tsv  (tree-sitter cognitive complexity)
#   compute_fanio.py       -> fanio-per-file.tsv                (Dart import-based fan-in/out)
#   compute_crap.py        -> crap-per-file.tsv                 (coverage only, if lcov.info exists)
#   compute_deadcode.py    -> deadcode-per-file.tsv             (if dead_code_analyzer is on PATH)
#   build_heatmap.py       -> codemap.tsv                       (joins git history + size + above)
#   render_heatmap.py      -> codemap.html                      (self-contained Plotly page)
#   render_codecity.py     -> codecity.html                     (Three.js CodeCity)
#   render_combined.py     -> combined.html                     (2D codemap <-> 3D city, linked)
#
# Bug signal: build_heatmap.py flags a commit as bug-linked by a subject-regex heuristic
# (HEATMAP_BUG_COMMIT_REGEX). When GITHUB_TOKEN/GH_TOKEN is set, this script also crawls
# the analysed repo's own GitHub "type: bug"/"type: regression" labels (fetch_bugs.py)
# for a second, more precise signal. Opt-in: GitHub's search API caps unauthenticated
# callers at 10 req/min.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export HEATMAP_REPO="${1:-${HEATMAP_REPO:-$(git rev-parse --show-toplevel)}}"
export HEATMAP_REPO="$(cd "$HEATMAP_REPO" && pwd)"
export HEATMAP_OUT="${2:-${HEATMAP_OUT:-$HEATMAP_REPO/.flutter-city}}"
export HEATMAP_PYLIBS="$SCRIPT_DIR/.pylibs"

if [ ! -d "$HEATMAP_PYLIBS" ]; then
  echo "[0/7] vendoring tree-sitter-dart into $HEATMAP_PYLIBS ..."
  pip3 install -q -r "$SCRIPT_DIR/requirements.txt" --target "$HEATMAP_PYLIBS"
fi

export HEATMAP_PRUNE="${HEATMAP_PRUNE:-.dart_tool,build,.git,.idea,.claude,.conductor,node_modules,.pub-cache,.flutter-plugins,.flutter-plugins-dependencies}"

export HEATMAP_TITLE="${HEATMAP_TITLE:-$(basename "$HEATMAP_REPO") Codemap}"
export CODECITY_TITLE="${CODECITY_TITLE:-flutter-city: $(basename "$HEATMAP_REPO")}"
export HEATMAP_OPEN_IN="${HEATMAP_OPEN_IN:-vscode}"

cd "$SCRIPT_DIR"
echo "repo: $HEATMAP_REPO"
echo "out:  $HEATMAP_OUT"
mkdir -p "$HEATMAP_OUT"

echo "[1/7] cognitive complexity ..."
python3 compute_complexity.py

echo "[2/7] fan-in / fan-out ..."
python3 compute_fanio.py

echo "[3/7] coverage (optional) ..."
python3 compute_crap.py

echo "[4/7] dead code (optional) ..."
python3 compute_deadcode.py

# Optional accurate bug signal (see header comment above): crawl the analysed repo's
# own GitHub bug labels into bug_issues.txt before build_heatmap.py reads it. Only
# attempted when a token is set and the repo's origin remote is a GitHub owner/repo.
# Never fatal: a failed or skipped crawl just leaves the subject heuristic alone.
if [ -n "${GITHUB_TOKEN:-}${GH_TOKEN:-}" ]; then
  ORIGIN_REPO="$(git -C "$HEATMAP_REPO" remote get-url origin 2>/dev/null \
    | sed -E 's#^(https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(\.git)?$#\2#')"
  if [ -n "$ORIGIN_REPO" ] && [[ "$ORIGIN_REPO" == */* ]]; then
    echo "[bugs] GITHUB_TOKEN set: crawling $ORIGIN_REPO's 'type: bug' / 'type: regression' issues ..."
    FETCH_BUGS_REPO="$ORIGIN_REPO" python3 fetch_bugs.py \
      || echo "[bugs] fetch_bugs.py failed; continuing with the subject-regex heuristic only" >&2
  else
    echo "[bugs] origin remote ($ORIGIN_REPO) is not a github.com owner/repo; skipping the label crawl" >&2
  fi
else
  echo "[bugs] no GITHUB_TOKEN/GH_TOKEN set; skipping the GitHub bug-label crawl" >&2
fi

echo "[5/7] joining codemap.tsv ..."
BUILD_HEATMAP_LOG="$(python3 build_heatmap.py 2>&1 | tee /dev/stderr)"

FILES=$(($(wc -l < "$HEATMAP_OUT/codemap.tsv") - 1))
COMMITS=$(git -C "$HEATMAP_REPO" rev-list --count HEAD)
BUGFIX="$(sed -n -E 's/.*walked [0-9]+ commits, ([0-9]+) flagged as bug-linked.*/\1/p' <<<"$BUILD_HEATMAP_LOG")"
BUGFIX="${BUGFIX:-0}"
export HEATMAP_SUBTITLE="${FILES} source Dart files · ${COMMITS} commits walked · ${BUGFIX} bug-fix commits."

echo "[6/7] rendering codemap.html + codecity.html ..."
python3 render_heatmap.py "$HEATMAP_OUT/codemap.tsv"
HEATMAP_TITLE="$CODECITY_TITLE" python3 render_codecity.py "$HEATMAP_OUT/codemap.tsv"

echo "[7/7] rendering combined.html ..."
python3 render_combined.py

echo "done -> $HEATMAP_OUT/codemap.html"
echo "city -> $HEATMAP_OUT/codecity.html"
echo "both -> $HEATMAP_OUT/combined.html"
