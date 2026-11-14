"""Đảo business rule trên nhánh local tạm, lưu log rồi phục hồi source.

Không commit/push mutation. Yêu cầu đang ở nhánh nhiệm vụ chứa Issue thật.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "backend/app/search/qdrant_store.py"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    branch = git("branch", "--show-current")
    match = re.fullmatch(r"(?:test|fix|feat)/(\d+)-.+", branch)
    if not match:
        raise SystemExit("Cần nhánh nhiệm vụ có Issue thật trước thí nghiệm mutation.")
    temporary_branch = f"test/{match.group(1)}-vt012-mutation-local-{uuid4().hex[:8]}"
    original = SOURCE.read_bytes()
    needle = b"if not _is_retryable_upsert_error(exc) or attempt == self.max_attempts:"
    replacement = b"if _is_retryable_upsert_error(exc) or attempt == self.max_attempts:"
    if original.count(needle) != 1:
        raise SystemExit("Không tìm thấy đúng một business rule để đảo.")
    before_hash = sha256(original).hexdigest()
    command = [sys.executable, "-m", "pytest", "backend/tests/harness/vt012/test_retry.py", "-q", "--tb=short"]
    subprocess.run(["git", "switch", "-c", temporary_branch], cwd=ROOT, check=True)
    try:
        SOURCE.write_bytes(original.replace(needle, replacement))
        result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / "mutation.log").write_text(result.stdout, encoding="utf-8")
    finally:
        SOURCE.write_bytes(original)
        subprocess.run(["git", "switch", branch], cwd=ROOT, check=True)
    after_hash = sha256(SOURCE.read_bytes()).hexdigest()
    report = {
        "baseline": git("rev-parse", "HEAD"),
        "submission_branch": branch,
        "temporary_branch": temporary_branch,
        "mutation": "invert truth of retryable business rule (remove not)",
        "original_rule": needle.decode(), "mutated_rule": replacement.decode(),
        "source_sha256_before": before_hash, "source_sha256_after": after_hash,
        "source_restored_exactly": before_hash == after_hash,
        "command": command, "exit_code": result.returncode,
        "mutation_killed": result.returncode == 1 and "FAILED" in result.stdout,
        "committed_or_pushed": False,
    }
    (output / "mutation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result.stdout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["mutation_killed"] and report["source_restored_exactly"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
