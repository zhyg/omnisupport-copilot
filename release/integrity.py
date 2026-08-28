"""Canonical hashing and optional signing for immutable release manifests."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> bytes:
    """Return stable UTF-8 JSON bytes suitable for hashing and signing."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def iter_artifact_digests(manifest: dict[str, Any]) -> Iterator[tuple[str, str, str]]:
    """Yield (scope, artifact path, expected digest) for every artifact the spec binds."""

    def walk(node: Any, trail: tuple[str, ...]) -> Iterator[tuple[str, str, str]]:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "artifact_digests" and isinstance(value, dict):
                    scope = ".".join(trail)
                    for path, digest in value.items():
                        yield scope, str(path), str(digest)
                else:
                    yield from walk(value, trail + (str(key),))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from walk(value, trail + (str(index),))

    yield from walk(manifest.get("spec") or {}, ())


def artifact_digest_drift(
    manifest: dict[str, Any], project_root: Path
) -> list[dict[str, str]]:
    """Report bound artifacts whose current content no longer matches the manifest.

    A manifest stays internally consistent after the code it describes changes, so the
    self digest alone cannot detect that a release no longer binds the working tree.
    """

    root = project_root.resolve()
    drift: list[dict[str, str]] = []
    for scope, raw_path, expected in iter_artifact_digests(manifest):
        record = {"scope": scope, "path": raw_path, "expected": expected}
        path = (root / raw_path).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            drift.append({**record, "status": "outside_project_root", "actual": ""})
            continue
        if not path.is_file():
            drift.append({**record, "status": "missing", "actual": ""})
            continue
        actual = file_digest(path)
        if not hmac.compare_digest(expected, actual):
            drift.append({**record, "status": "mismatch", "actual": actual})
    return drift


def verify_artifact_digests(manifest: dict[str, Any], project_root: Path) -> None:
    drift = artifact_digest_drift(manifest, project_root)
    if drift:
        detail = ", ".join(f"{item['path']} ({item['status']})" for item in drift)
        raise ValueError(f"release artifact digests no longer match the tree: {detail}")


def manifest_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the signed body; integrity metadata never signs itself."""

    payload = copy.deepcopy(manifest)
    payload.pop("integrity", None)
    return payload


def finalize_manifest(
    manifest: dict[str, Any],
    *,
    signing_key: bytes | None = None,
    key_id: str | None = None,
) -> dict[str, Any]:
    result = copy.deepcopy(manifest_payload(manifest))
    digest = sha256_digest(canonical_json(result))
    if signing_key:
        signature = hmac.new(signing_key, digest.encode("ascii"), hashlib.sha256).hexdigest()
        signing = {
            "algorithm": "hmac-sha256",
            "key_id": key_id or "local-week14",
            "value": signature,
        }
    else:
        signing = {"algorithm": "none", "key_id": None, "value": None}
    result["integrity"] = {"manifest_digest": digest, "signature": signing}
    return result


def verify_manifest_digest(manifest: dict[str, Any]) -> None:
    integrity = manifest.get("integrity") or {}
    expected = integrity.get("manifest_digest")
    actual = sha256_digest(canonical_json(manifest_payload(manifest)))
    if not expected or not hmac.compare_digest(str(expected), actual):
        raise ValueError("release manifest digest mismatch")


def verify_manifest(manifest: dict[str, Any], *, signing_key: bytes | None = None) -> None:
    verify_manifest_digest(manifest)
    integrity = manifest["integrity"]
    actual = integrity["manifest_digest"]

    signature = integrity.get("signature") or {}
    algorithm = signature.get("algorithm")
    if algorithm == "none":
        if signing_key is not None:
            raise ValueError("release manifest is unsigned")
        return
    if algorithm != "hmac-sha256":
        raise ValueError(f"unsupported signature algorithm: {algorithm!r}")
    if signing_key is None:
        raise ValueError("signing key is required to verify this release manifest")
    expected_signature = hmac.new(signing_key, actual.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(signature.get("value") or ""), expected_signature):
        raise ValueError("release manifest signature mismatch")
