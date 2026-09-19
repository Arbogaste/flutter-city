#!/usr/bin/env python3
# Adapted from code-city (https://github.com/victorrentea/code-city), Unlicense.
"""Sonar-style Cognitive Complexity for Dart/Flutter codebases, via tree-sitter-dart.

Implements https://www.sonarsource.com/docs/CognitiveComplexity.pdf against
tree-sitter-dart's grammar. See docs/superpowers/specs/2026-09-19-flutter-city-design.md
for the grammar-shape notes and the deliberate simplifications vs. the Java version
this was adapted from (closures don't add nesting; no recursion/labeled-break bonus).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional
import subprocess

import repo_files

_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.environ.get("HEATMAP_PYLIBS"), os.path.join(_here, ".pylibs")):
    if _p and os.path.isdir(_p):
        sys.path.insert(0, _p)
import tree_sitter_dart as tsd
from tree_sitter import Language, Parser

try:
    DART = Language(tsd.language())
except TypeError:
    DART = Language(tsd.language(), "dart")

parser = Parser(DART)

CLASS_LIKE = {"class_definition", "mixin_declaration", "extension_declaration", "enum_declaration"}

LOGICAL_TYPES = {"logical_and_expression", "logical_or_expression"}
LOGICAL_OP_OF = {"logical_and_expression": "&&", "logical_or_expression": "||"}


def _git_root(start):
    try:
        return subprocess.check_output(
            ["git", "-C", start, "rev-parse", "--show-toplevel"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return start


REPO = Path(os.environ.get("HEATMAP_REPO") or _git_root(_here)).resolve()
OUT_DIR = Path(os.environ.get("HEATMAP_OUT") or str(REPO)).resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)


def node_text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def get_name(node, src: bytes) -> Optional[str]:
    n = node.child_by_field_name("name")
    if n is not None:
        return node_text(n, src)
    for c in node.children:
        if c.type == "identifier":
            return node_text(c, src)
    return None


def boolean_groups(expr) -> int:
    """Sonar 'distinct contiguous runs' of &&/|| for one top-of-chain expression.

    Total = 1 + (number of operator changes walking the chain left to right).
    """
    ops: list[str] = []

    def collect(n):
        if n.type in LOGICAL_TYPES:
            left, right = n.children[0], n.children[-1]
            collect(left)
            ops.append(LOGICAL_OP_OF[n.type])
            collect(right)
            return
        return

    collect(expr)
    if not ops:
        return 0
    groups = 1
    for i in range(1, len(ops)):
        if ops[i] != ops[i - 1]:
            groups += 1
    return groups


def is_top_level_boolean(expr) -> bool:
    p = expr.parent
    if p is None:
        return True
    return p.type not in LOGICAL_TYPES


def compute_method_complexity(body) -> int:
    total = 0

    def walk_else(alt, nesting):
        """The alternative branch of an if: another if_statement (else-if,
        chained without extra nesting) or a plain block (else, nested +1)."""
        nonlocal total
        if alt.type == "if_statement":
            total += 1  # else-if: fresh +1, no extra nesting
            cons2 = alt.child_by_field_name("consequence")
            alt2 = alt.child_by_field_name("alternative")
            for c in alt.children:
                if c != cons2 and c != alt2:
                    walk(c, nesting)
            if cons2 is not None:
                walk(cons2, nesting + 1)
            if alt2 is not None:
                walk_else(alt2, nesting)
        else:
            total += 1  # plain else
            walk(alt, nesting + 1)

    def walk(node, nesting: int):
        nonlocal total
        t = node.type

        if t in CLASS_LIKE or t in ("method_signature", "function_signature"):
            return  # nested declarations score under their own unit

        if t == "if_statement":
            total += 1 + nesting
            cons = node.child_by_field_name("consequence")
            alt = node.child_by_field_name("alternative")
            for c in node.children:
                if c != cons and c != alt:
                    walk(c, nesting)
            if cons is not None:
                walk(cons, nesting + 1)
            if alt is not None:
                walk_else(alt, nesting)
            return

        if t == "conditional_expression":
            total += 1 + nesting
            cons = node.child_by_field_name("consequence")
            alt = node.child_by_field_name("alternative")
            for c in node.children:
                if c != cons and c != alt:
                    walk(c, nesting)
            if cons is not None:
                walk(cons, nesting + 1)
            if alt is not None:
                walk(alt, nesting + 1)
            return

        if t in ("for_statement", "while_statement", "do_statement"):
            total += 1 + nesting
            body_n = node.child_by_field_name("body")
            for c in node.children:
                if c == body_n:
                    walk(c, nesting + 1)
                else:
                    walk(c, nesting)
            return

        if t == "switch_statement":
            total += 1 + nesting
            body_n = node.child_by_field_name("body")
            for c in node.children:
                if c == body_n:
                    walk(c, nesting + 1)
                else:
                    walk(c, nesting)
            return

        if t == "try_statement":
            body_n = node.child_by_field_name("body")
            children = list(node.children)
            i = 0
            while i < len(children):
                c = children[i]
                if c == body_n:
                    walk(c, nesting)
                elif c.type == "catch_clause":
                    total += 1 + nesting
                    walk(c, nesting + 1)
                    # catch's body is the very next sibling block, not a child of catch_clause
                    if i + 1 < len(children) and children[i + 1].type == "block":
                        walk(children[i + 1], nesting + 1)
                        i += 1
                elif c.type == "finally_clause":
                    walk(c, nesting)
                else:
                    walk(c, nesting)
                i += 1
            return

        if t in LOGICAL_TYPES and is_top_level_boolean(node):
            total += boolean_groups(node)
            # still recurse to find nested constructs (calls, ternaries) inside operands
            for c in node.children:
                walk(c, nesting)
            return

        for c in node.children:
            walk(c, nesting)

    walk(body, 0)
    return total


def _member_pairs(container_body):
    """Yield (signature_node, body_node) for every method-like member in a
    class_body/program: `method_signature`/`function_signature` immediately
    followed by a `function_body` sibling. Bodiless constructors (wrapped in
    a `declaration` node) are skipped — nothing to score."""
    children = list(container_body.children)
    for i, c in enumerate(children):
        if c.type in ("method_signature", "function_signature"):
            if i + 1 < len(children) and children[i + 1].type == "function_body":
                yield c, children[i + 1]


def complexity_of_source(src: bytes) -> int:
    """Cognitive complexity of one Dart source blob, with no file on disk."""
    tree = parser.parse(src)
    total = 0

    def walk_container(container):
        nonlocal total
        for sig, body in _member_pairs(container):
            total += compute_method_complexity(body)

    def find_bodies(node):
        if node.type == "class_body":
            walk_container(node)
        for c in node.children:
            find_bodies(c)

    walk_container(tree.root_node)  # top-level functions
    find_bodies(tree.root_node)     # class/mixin/extension members
    return total


def collect_classes(root, src: bytes):
    """Yield (name, class-like node) for every class/mixin/extension/enum at top level."""
    for c in root.children:
        if c.type in CLASS_LIKE:
            yield get_name(c, src) or "<anon>", c


def process_file(abs_path: Path):
    try:
        src = abs_path.read_bytes()
    except OSError as e:
        print(f"warn: cannot read {abs_path}: {e}", file=sys.stderr)
        return [], (str(abs_path.relative_to(REPO)), 0, 0, 0), True

    tree = parser.parse(src)
    root = tree.root_node
    parse_error = root.has_error
    rel = str(abs_path.relative_to(REPO))

    classes = list(collect_classes(root, src))
    per_class_rows = []
    file_complexity = 0
    file_method_count = 0

    for name, cnode in classes:
        body = cnode.child_by_field_name("body")
        c_complexity = 0
        m_count = 0
        if body is not None:
            for sig, mbody in _member_pairs(body):
                c_complexity += compute_method_complexity(mbody)
                m_count += 1
        per_class_rows.append((rel, name, c_complexity, m_count))
        file_complexity += c_complexity
        file_method_count += m_count

    # top-level functions belong to the file, not to any class
    top_level_complexity = 0
    top_level_count = 0
    for sig, body in _member_pairs(root):
        top_level_complexity += compute_method_complexity(body)
        top_level_count += 1
    if top_level_count:
        per_class_rows.append((rel, "<top-level>", top_level_complexity, top_level_count))
        file_complexity += top_level_complexity
        file_method_count += top_level_count

    per_file_row = (rel, file_complexity, len(classes), file_method_count)
    return per_class_rows, per_file_row, parse_error


def main():
    dart_files = [Path(p) for p in repo_files.dart_sources(str(REPO))]

    per_class_path = OUT_DIR / "complexity-per-class.tsv"
    per_file_path = OUT_DIR / "complexity-per-file.tsv"

    error_files = 0
    all_class_rows: list[tuple[str, str, int, int]] = []
    all_file_rows: list[tuple[str, int, int, int]] = []

    for i, p in enumerate(dart_files):
        rows, frow, err = process_file(p)
        if err:
            error_files += 1
            print(f"warn: parse errors in {p.relative_to(REPO)}", file=sys.stderr)
        all_class_rows.extend(rows)
        all_file_rows.append(frow)
        if (i + 1) % 500 == 0:
            print(f"... processed {i + 1}/{len(dart_files)}", file=sys.stderr)

    with per_class_path.open("w", encoding="utf-8") as f:
        f.write("file\tclass_fqn\tclass_complexity\tmethod_count\n")
        for r in all_class_rows:
            f.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\n")

    with per_file_path.open("w", encoding="utf-8") as f:
        f.write("file\tfile_complexity\tclass_count\tmethod_count\n")
        for r in all_file_rows:
            f.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\n")

    print("\n=== Summary ===")
    print(f"Files processed: {len(dart_files)}")
    print(f"Files with parse errors: {error_files}")
    print(f"Total methods/functions: {sum(r[3] for r in all_file_rows)}")


if __name__ == "__main__":
    main()
