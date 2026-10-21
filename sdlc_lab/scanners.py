"""Vendor-neutral scanner ingestion adapters and deterministic verification layer.

Converts standardized outputs from tools like Gitleaks, OSV-Scanner, Semgrep,
and Ruff/Linters into normalized, schema-validated Finding objects.
"""

from typing import Any, Dict, List, Optional
from .schemas import Finding


def mask_secret(value: str) -> str:
    """Mask sensitive string content to prevent secret leakage in reports/logs."""
    if not value:
        return "[EMPTY]"
    if len(value) <= 6:
        return "[REDACTED]"
    return f"{value[:2]}...[REDACTED]...{value[-2:]}"


class ScannerIngestor:
    """Parses heterogeneous deterministic scanner outputs into standard Finding objects."""

    @staticmethod
    def parse_gitleaks(report: Dict[str, Any]) -> List[Finding]:
        """Ingest Gitleaks JSON report.
        
        Expected structure: list of leak records or {'leaks': [...]}
        """
        findings = []
        leaks = report if isinstance(report, list) else report.get("leaks", [])
        for i, leak in enumerate(leaks, 1):
            rule_id = leak.get("RuleID", leak.get("rule_id", "generic-secret"))
            file_path = leak.get("File", leak.get("file", "unknown"))
            start_line = leak.get("StartLine", leak.get("start_line"))
            secret_match = leak.get("Secret", leak.get("match", ""))
            desc = leak.get("Description", leak.get("description", "Potential hardcoded secret detected."))

            findings.append(Finding(
                finding_id=f"DET-GITLEAKS-{i:03d}",
                category="secret_exposure",
                severity="critical",
                confidence="high",
                summary=f"Secret detected by Gitleaks: {rule_id}",
                evidence=f"Pattern '{rule_id}' matched in {file_path}:{start_line} (secret: {mask_secret(secret_match)})",
                explanation=desc,
                recommendation="Remove the hardcoded secret immediately. Rotate any exposed credentials and use an environment variable or secrets manager.",
                confirmed_by_deterministic_tool=True,
                source_tool="gitleaks",
                file_path=file_path,
                line_number=int(start_line) if start_line and str(start_line).isdigit() else None
            ))
        return findings

    @staticmethod
    def parse_semgrep(report: Dict[str, Any]) -> List[Finding]:
        """Ingest Semgrep JSON report.
        
        Expected structure: {'results': [{'check_id': ..., 'path': ..., 'start': {'line': ...}, 'extra': {'message': ..., 'severity': ...}}]}
        """
        findings = []
        results = report.get("results", []) if isinstance(report, dict) else (report if isinstance(report, list) else [])
        for i, res in enumerate(results, 1):
            check_id = res.get("check_id", "semgrep-rule")
            path = res.get("path", "unknown")
            start = res.get("start", {})
            line = start.get("line") if isinstance(start, dict) else None
            extra = res.get("extra", {})
            message = extra.get("message", "Semgrep security or quality rule triggered.")
            raw_severity = str(extra.get("severity", "WARNING")).upper()

            # Map Semgrep severity to schema severity
            severity_map = {
                "ERROR": "high",
                "WARNING": "medium",
                "INFO": "low",
                "CRITICAL": "critical"
            }
            severity = severity_map.get(raw_severity, "medium")

            # Determine category
            category = "code_vulnerability"
            if "auth" in check_id.lower() or "auth" in message.lower():
                category = "authorization_gap"
            elif "injection" in check_id.lower() or "sql" in check_id.lower():
                category = "injection_risk"
            elif "eval" in check_id.lower():
                category = "dangerous_dynamic_execution"

            findings.append(Finding(
                finding_id=f"DET-SEMGREP-{i:03d}",
                category=category,
                severity=severity,
                confidence="high",
                summary=f"Semgrep rule violation: {check_id}",
                evidence=f"Static analyzer rule '{check_id}' triggered at {path}:{line}",
                explanation=message,
                recommendation=extra.get("fix", "Review finding against secure coding standards and refactor code."),
                confirmed_by_deterministic_tool=True,
                source_tool="semgrep",
                file_path=path,
                line_number=int(line) if line and str(line).isdigit() else None
            ))
        return findings

    @staticmethod
    def parse_osv(report: Dict[str, Any]) -> List[Finding]:
        """Ingest OSV-Scanner JSON report.
        
        Expected structure: {'results': [{'packages': [{'package': {'name': ..., 'version': ...}, 'vulnerabilities': [...]}]}]}
        """
        findings = []
        results = report.get("results", []) if isinstance(report, dict) else []
        count = 1
        for res in results:
            packages = res.get("packages", [])
            for pkg_entry in packages:
                pkg = pkg_entry.get("package", {})
                pkg_name = pkg.get("name", "unknown")
                pkg_version = pkg.get("version", "unknown")
                vulns = pkg_entry.get("vulnerabilities", [])
                for vuln in vulns:
                    vuln_id = vuln.get("id", "OSV-VULN")
                    summary = vuln.get("summary", f"Vulnerability {vuln_id} in {pkg_name}@{pkg_version}")
                    
                    # Extract severity
                    severity = "high"
                    database_specific = vuln.get("database_specific", {})
                    if "severity" in database_specific:
                        raw_sev = str(database_specific["severity"]).lower()
                        if raw_sev in {"critical", "high", "medium", "low"}:
                            severity = raw_sev

                    findings.append(Finding(
                        finding_id=f"DET-OSV-{count:03d}",
                        category="vulnerable_dependency",
                        severity=severity,
                        confidence="high",
                        summary=f"Dependency vulnerability in {pkg_name} ({vuln_id})",
                        evidence=f"Package {pkg_name} version {pkg_version} matches known advisory {vuln_id}",
                        explanation=summary,
                        recommendation=f"Upgrade package '{pkg_name}' to a patched release.",
                        confirmed_by_deterministic_tool=True,
                        source_tool="osv-scanner",
                        file_path=res.get("source", {}).get("path", "requirements.txt"),
                        line_number=None
                    ))
                    count += 1
        return findings

    @staticmethod
    def parse_linters(report: Dict[str, Any]) -> List[Finding]:
        """Ingest Python / JS linter reports (e.g. Ruff, Flake8, ESLint).
        
        Expected structure: list of issue dicts or {'issues': [...]}
        """
        findings = []
        issues = report if isinstance(report, list) else report.get("issues", [])
        for i, issue in enumerate(issues, 1):
            tool = issue.get("tool", "linter")
            code = issue.get("code", "LINT-001")
            file_path = issue.get("filename", issue.get("file", "unknown"))
            line = issue.get("line_number", issue.get("line"))
            message = issue.get("message", "Linting rule violation.")

            findings.append(Finding(
                finding_id=f"DET-LINT-{i:03d}",
                category="code_quality_lint",
                severity="low",
                confidence="high",
                summary=f"Linter warning ({code}) via {tool}",
                evidence=f"{tool} reported {code} at {file_path}:{line}",
                explanation=message,
                recommendation="Fix formatting/lint style to comply with team standards.",
                confirmed_by_deterministic_tool=True,
                source_tool=tool,
                file_path=file_path,
                line_number=int(line) if line and str(line).isdigit() else None
            ))
        return findings


def normalize_all_scanner_reports(raw_reports: Optional[Dict[str, Any]]) -> List[Finding]:
    """Ingest multiple tool outputs into a unified list of verified findings."""
    if not raw_reports:
        return []

    verified_findings: List[Finding] = []
    if "gitleaks" in raw_reports:
        verified_findings.extend(ScannerIngestor.parse_gitleaks(raw_reports["gitleaks"]))
    if "semgrep" in raw_reports:
        verified_findings.extend(ScannerIngestor.parse_semgrep(raw_reports["semgrep"]))
    if "osv" in raw_reports:
        verified_findings.extend(ScannerIngestor.parse_osv(raw_reports["osv"]))
    if "linters" in raw_reports:
        verified_findings.extend(ScannerIngestor.parse_linters(raw_reports["linters"]))

    return verified_findings
