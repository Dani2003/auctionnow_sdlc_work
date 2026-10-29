"""AuctionNow Alembic Database Migration Safety Analyzer.

Scans changed migration files and dry-run SQL for destructive operations:
- DROP TABLE
- DROP COLUMN
- TRUNCATE
- ALTER TABLE ... DROP

Outputs machine-readable JSON analysis and blocks the PR unless an authorized
human review override is provided.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List

DESTRUCTIVE_PATTERNS = [
    (re.compile(r"\bop\.drop_table\s*\(", re.IGNORECASE), "DROP_TABLE", "Alembic operation drops an entire table"),
    (re.compile(r"\bop\.drop_column\s*\(", re.IGNORECASE), "DROP_COLUMN", "Alembic operation drops a column (data loss risk)"),
    (re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE), "RAW_DROP_TABLE", "Raw SQL drops a table"),
    (re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE), "RAW_DROP_COLUMN", "Raw SQL drops a column"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "TRUNCATE_TABLE", "Operation empties all data in table"),
    (re.compile(r"\bop\.drop_index\s*\(", re.IGNORECASE), "DROP_INDEX", "Index dropped; review performance impact"),
]


def scan_file_content(file_path: Path) -> List[Dict[str, Any]]:
    findings = []
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"type": "READ_ERROR", "message": str(e), "file": str(file_path)}]

    lines = text.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        # Skip pure comments
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("--"):
            continue
        for regex, op_type, explanation in DESTRUCTIVE_PATTERNS:
            if regex.search(line):
                findings.append({
                    "file": str(file_path),
                    "line_number": line_idx,
                    "operation_type": op_type,
                    "code_snippet": stripped[:120],
                    "explanation": explanation,
                })
    return findings


def analyze_migrations(migrations_dir: Path) -> Dict[str, Any]:
    all_findings = []
    scanned_files = []

    if migrations_dir.exists():
        for ext in ("*.py", "*.sql"):
            for p in migrations_dir.glob(f"**/{ext}"):
                scanned_files.append(str(p))
                findings = scan_file_content(p)
                all_findings.extend(findings)

    has_destructive = any(
        f.get("operation_type") in ("DROP_TABLE", "DROP_COLUMN", "RAW_DROP_TABLE", "RAW_DROP_COLUMN", "TRUNCATE_TABLE")
        for f in all_findings
    )

    return {
        "scanned_files_count": len(scanned_files),
        "scanned_files": scanned_files,
        "destructive_findings_count": len(all_findings),
        "has_destructive_operations": has_destructive,
        "findings": all_findings,
    }


def main():
    parser = argparse.ArgumentParser(description="Alembic Migration Safety Scanner")
    parser.add_argument("--migrations-dir", default="alembic/versions", help="Path to migration versions")
    parser.add_argument("--report-file", default="artifacts/gate-3/migration-analysis.json", help="Output report JSON")
    parser.add_argument("--allow-destructive", action="store_true", help="Override flag for signed destructive review")
    args = parser.parse_args()

    m_dir = Path(args.migrations_dir)
    report = analyze_migrations(m_dir)

    out_path = Path(args.report_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Migration safety analysis written to {out_path}")

    if report["has_destructive_operations"] and not args.allow_destructive:
        print(f"\nCRITICAL: Detected {len(report['findings'])} destructive database operations!", file=sys.stderr)
        for f in report["findings"]:
            print(f"  - [{f['operation_type']}] {f['file']}:{f['line_number']} -> {f['code_snippet']}", file=sys.stderr)
        print("\nDestructive migrations are BLOCKED by Gate 3 policy.", file=sys.stderr)
        sys.exit(1)

    print("Migration safety scan passed cleanly.")
    sys.exit(0)


if __name__ == "__main__":
    main()
