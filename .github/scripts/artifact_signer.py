"""AuctionNow Cryptographic Gate Attestation Engine.

Generates and verifies tamper-evident gate execution attestations.
Binds gate results to the exact candidate commit SHA using HMAC-SHA256.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import sys


def compute_signature(secret: str, gate_id: str, status: str, commit_sha: str, timestamp: str) -> str:
    message = f"{gate_id}:{status}:{commit_sha}:{timestamp}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def sign_gate(gate_id: str, status: str, commit_sha: str, secret: str, output_path: Path):
    timestamp = datetime.now(timezone.utc).isoformat()
    signature = compute_signature(secret, gate_id, status, commit_sha, timestamp)
    
    payload = {
        "gate_id": gate_id,
        "status": status,
        "commit_sha": commit_sha,
        "timestamp_utc": timestamp,
        "hmac_sha256": signature,
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Attestation successfully minted for {gate_id} at {output_path}")


def verify_gate(attestation_path: Path, expected_commit: str, secret: str):
    if not attestation_path.exists():
        print(f"CRITICAL: Attestation file not found at {attestation_path}", file=sys.stderr)
        sys.exit(1)
        
    try:
        data = json.loads(attestation_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"CRITICAL: Failed to parse attestation JSON: {e}", file=sys.stderr)
        sys.exit(1)

    gate_id = data.get("gate_id")
    status = data.get("status")
    commit_sha = data.get("commit_sha")
    timestamp = data.get("timestamp_utc")
    provided_signature = data.get("hmac_sha256")

    # 1. Verify commit binding
    if commit_sha != expected_commit:
        print(
            f"SECURITY ERROR: Attestation commit mismatch!\n"
            f"Expected: {expected_commit}\nAttestation has: {commit_sha}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 2. Verify status was success
    if status.lower() not in ("success", "pass"):
        print(f"SECURITY ERROR: Prior gate {gate_id} status is '{status}'. Cannot proceed.", file=sys.stderr)
        sys.exit(1)

    # 3. Verify cryptographic HMAC signature
    expected_sig = compute_signature(secret, gate_id, status, commit_sha, timestamp)
    if not hmac.compare_digest(provided_signature, expected_sig):
        print("SECURITY ERROR: HMAC cryptographic signature mismatch! Attestation was tampered with.", file=sys.stderr)
        sys.exit(1)

    print(f"VERIFIED: Gate {gate_id} passed cleanly on commit {commit_sha[:10]}.")


def main():
    parser = argparse.ArgumentParser(description="Cryptographic Gate Attestation Signer & Verifier")
    parser.add_argument("--verify", action="store_true", help="Run verification mode")
    parser.add_argument("--gate-id", help="Identifier of the gate (e.g. gate-1-quality-security)")
    parser.add_argument("--status", help="Execution status (success, failure)")
    parser.add_argument("--commit-sha", help="Current git commit SHA")
    parser.add_argument("--secret", required=True, help="HMAC signing secret key")
    parser.add_argument("--output", type=Path, help="Target file path to write attestation JSON")
    parser.add_argument("--attestation", type=Path, help="Path to attestation file for verification")
    parser.add_argument("--expected-commit", help="Commit SHA expected during verification")
    args = parser.parse_args()

    if args.verify:
        if not args.attestation or not args.expected_commit:
            print("Error: --attestation and --expected-commit required for verification.", file=sys.stderr)
            sys.exit(1)
        verify_gate(args.attestation, args.expected_commit, args.secret)
    else:
        if not all([args.gate_id, args.status, args.commit_sha, args.output]):
            print("Error: --gate-id, --status, --commit-sha, and --output required for signing.", file=sys.stderr)
            sys.exit(1)
        sign_gate(args.gate_id, args.status, args.commit_sha, args.secret, args.output)


if __name__ == "__main__":
    main()
