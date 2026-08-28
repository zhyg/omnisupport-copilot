"""Pre-release check that a governed manifest still binds the current working tree."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from release.integrity import artifact_digest_drift, verify_manifest
from release.policy import validate_release_policy
from release.schema import validate_manifest_schema


def verify_release_manifest(
    manifest: dict[str, Any],
    *,
    project_root: Path,
    signing_key: bytes | None = None,
) -> list[dict[str, str]]:
    """Validate schema, self digest and policy, then report artifact digest drift."""

    validate_manifest_schema(manifest)
    verify_manifest(manifest, signing_key=signing_key)
    validate_release_policy(manifest)
    return artifact_digest_drift(manifest, project_root)


def _head_sha(project_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _check(manifest_path: Path, project_root: Path, signing_key: bytes | None) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = manifest.get("metadata") or {}
    head = _head_sha(project_root)
    report: dict[str, Any] = {
        "manifest": str(manifest_path),
        "release_id": metadata.get("release_id"),
        "git_sha": metadata.get("git_sha"),
        "head_sha": head,
        # None keeps "git unavailable" distinguishable from "manifest is behind HEAD".
        "git_sha_is_head": None if head is None else metadata.get("git_sha") == head,
    }
    try:
        drift = verify_release_manifest(
            manifest, project_root=project_root, signing_key=signing_key
        )
    except ValueError as exc:
        return {**report, "status": "fail", "reason": str(exc), "drift": []}
    report["drift"] = drift
    report["status"] = "fail" if drift else "ok"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify governed release manifests against the working tree"
    )
    parser.add_argument("manifests", type=Path, nargs="+")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--signing-key-env", default="WEEK14_RELEASE_SIGNING_KEY")
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    signing_value = os.getenv(args.signing_key_env, "")
    signing_key = signing_value.encode("utf-8") if signing_value else None
    reports = [_check(path, project_root, signing_key) for path in args.manifests]
    failed = [report for report in reports if report["status"] != "ok"]
    print(
        json.dumps(
            {
                "status": "fail" if failed else "ok",
                "checked": len(reports),
                "failed": len(failed),
                "reports": reports,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
