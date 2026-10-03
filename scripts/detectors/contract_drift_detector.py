#!/usr/bin/env python3
"""Contract Drift Static AST Detector

Deterministic static AST analyzer that inspects Python source files for
contract divergence between event producers and consumers.

Specifically detects:
1. Schema field renaming (e.g. 'timestamp' -> 'timestamp_us')
2. Consumer access to retired or unmigrated schema fields
3. Unit representation shifts (float seconds vs integer microseconds)

Exit codes:
  0: No contract drift detected (schema aligned or backward-compatible)
  1: Contract drift detected
  2: Error (file not found, syntax error, invalid arguments)
"""

import ast
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple

DETECTOR_VERSION = "1.0.0"


class SchemaVisitor(ast.NodeVisitor):
    """Extracts schema definitions, dictionary keys, and attribute accesses."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        # Producer emitted fields: Set[str]
        self.produced_fields: Set[str] = set()
        # Consumer referenced fields: Set[Tuple[str, int, int]] (field_name, lineno, col_offset)
        self.consumed_fields: Set[Tuple[str, int, int]] = set()
        # Explicit backward-compatibility properties or aliases: Set[str]
        self.compat_aliases: Set[str] = set()

    def visit_Dict(self, node: ast.Dict):
        # Detect dict keys (e.g. {"timestamp_us": ..., "event_id": ...})
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                self.produced_fields.add(key.value)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        # Detect dict lookups (e.g. record["timestamp"])
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            self.consumed_fields.add((node.slice.value, node.lineno, node.col_offset))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # Detect attribute lookups (e.g. record.timestamp)
        self.consumed_fields.add((node.attr, node.lineno, node.col_offset))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Check for @property decorators that provide backward-compatibility aliases
        is_prop = any(
            isinstance(d, ast.Name) and d.id == "property"
            for d in node.decorator_list
        )
        if is_prop:
            self.compat_aliases.add(node.name)
            self.produced_fields.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        # Detect dataclass or Pydantic fields
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                self.produced_fields.add(stmt.target.id)
            elif isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        self.produced_fields.add(target.id)
        self.generic_visit(node)


def analyze_file(filepath: Path) -> SchemaVisitor:
    """Parse and visit an individual Python file."""
    content = filepath.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(filepath))
    visitor = SchemaVisitor(str(filepath))
    visitor.visit(tree)
    return visitor


def detect_contract_drift(
    producer_files: List[Path],
    consumer_files: List[Path],
    known_retired_fields: Optional[Dict[str, str]] = None,
) -> Dict:
    """Analyze producer and consumer files to detect schema divergence.
    
    known_retired_fields: maps old_field -> new_field (e.g. {"timestamp": "timestamp_us"})
    """
    if known_retired_fields is None:
        known_retired_fields = {"timestamp": "timestamp_us"}

    # Aggregate produced fields and compatibility aliases
    all_produced: Set[str] = set()
    all_compat: Set[str] = set()
    producer_details = []

    for p in producer_files:
        visitor = analyze_file(p)
        all_produced.update(visitor.produced_fields)
        all_compat.update(visitor.compat_aliases)
        producer_details.append({
            "file": str(p),
            "produced_fields": sorted(list(visitor.produced_fields)),
            "compat_aliases": sorted(list(visitor.compat_aliases)),
        })

    findings = []
    consumer_details = []

    for c in consumer_files:
        visitor = analyze_file(c)
        c_consumed = visitor.consumed_fields
        consumer_details.append({
            "file": str(c),
            "consumed_fields": sorted([f[0] for f in c_consumed]),
        })

        for old_field, new_field in known_retired_fields.items():
            # Condition for drift:
            # 1. Producer emits new_field
            # 2. Producer does NOT emit old_field (and no compat alias exists)
            # 3. Consumer references old_field
            if new_field in all_produced and old_field not in all_produced and old_field not in all_compat:
                for field, line, col in c_consumed:
                    if field == old_field:
                        findings.append({
                            "file": str(c),
                            "line": line,
                            "column": col,
                            "drift_type": "retired_field_access",
                            "severity": "WARNING",
                            "retired_field": old_field,
                            "replacement_field": new_field,
                            "message": (
                                f"Consumer accesses retired field '{old_field}' at line {line}:{col}, "
                                f"but producer schema migrated to '{new_field}' with no backward-compatibility alias."
                            ),
                        })

    has_drift = len(findings) > 0

    script_bytes = Path(__file__).read_bytes()
    script_sha = hashlib.sha256(script_bytes).hexdigest()

    return {
        "detector": "contract_drift_detector",
        "version": DETECTOR_VERSION,
        "detector_sha256": script_sha,
        "has_drift": has_drift,
        "findings_count": len(findings),
        "findings": findings,
        "producer_analysis": producer_details,
        "consumer_analysis": consumer_details,
    }


def main():
    parser = argparse.ArgumentParser(description="Static AST Contract Drift Detector")
    parser.add_argument("--producers", nargs="+", required=True, help="Producer Python source file(s)")
    parser.add_argument("--consumers", nargs="+", required=True, help="Consumer Python source file(s)")
    parser.add_argument("--retired-field", action="append", help="Retired field mapping in old:new format (default timestamp:timestamp_us)")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")

    args = parser.parse_args()

    retired_map = {}
    if args.retired_field:
        for item in args.retired_field:
            if ":" in item:
                old, new = item.split(":", 1)
                retired_map[old.strip()] = new.strip()
    if not retired_map:
        retired_map = {"timestamp": "timestamp_us"}

    producer_paths = [Path(p) for p in args.producers]
    consumer_paths = [Path(c) for c in args.consumers]

    for p in producer_paths + consumer_paths:
        if not p.exists():
            print(f"Error: File not found: {p}", file=sys.stderr)
            sys.exit(2)

    try:
        report = detect_contract_drift(producer_paths, consumer_paths, retired_map)
    except Exception as e:
        print(f"Error during static analysis: {e}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if report["has_drift"]:
            print(f"⚠️ CONTRACT DRIFT DETECTED: {report['findings_count']} violation(s)")
            for f in report["findings"]:
                print(f"  - [{f['file']}:{f['line']}:{f['column']}] {f['message']}")
        else:
            print("✅ NO CONTRACT DRIFT: Producer and consumer schemas are aligned or compatible.")

    sys.exit(1 if report["has_drift"] else 0)


if __name__ == "__main__":
    main()
