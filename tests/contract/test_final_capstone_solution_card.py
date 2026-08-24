from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/rag_api"))

from app.models.rag_models import ProposedAction, SolutionCardResponse  # noqa: E402
from app.solution_card import needs_clarification, proposed_action_for  # noqa: E402
from pipelines.query.rewriter import extract_protected_terms  # noqa: E402


def test_solution_card_schema_accepts_only_the_frozen_contract():
    schema = json.loads((ROOT / "contracts/product/solution_card.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    value = {
        "summary": "HTTP 401 indicates signature verification failed.",
        "steps": ["Verify the raw body.", "Use dual-secret rotation."],
        "citations": [{"evidence_id": "ev-1", "source": "doc:capstone:webhook-signature-rotation"}],
        "confidence": 0.9,
        "needs_clarification": False,
        "abstain_reason": None,
        "proposed_action": {"operation": "none", "control": "none"},
        "release_id": "capstone-v1",
        "trace_id": "trace-1",
    }
    jsonschema.Draft202012Validator(schema).validate(value)
    SolutionCardResponse.model_validate(value)
    invalid = dict(value, invented_field=True)
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(invalid))
    assert errors


def test_action_policy_is_server_side_and_control_is_fixed():
    assert proposed_action_for("please add internal note", abstain_reason=None) == ProposedAction(
        operation="add_internal_note", control="confirm"
    )
    assert proposed_action_for("grant service credit", abstain_reason=None) == ProposedAction(
        operation="grant_service_credit", control="hitl"
    )
    assert proposed_action_for("grant service credit", abstain_reason="no_retrieval_results") == ProposedAction(
        operation="none", control="none"
    )


def test_webhook_ambiguity_requires_a_concrete_identifier():
    assert needs_clarification("Webhook 不工作了，怎么修？", has_evidence=True)
    assert not needs_clarification(
        "Workspace 4.2 的 WS-WEBHOOK-401 返回 HTTP 401", has_evidence=True
    )


def test_unknown_webhook_code_is_a_protected_identifier():
    assert "WS-QUANTUM-999" in extract_protected_terms(
        "Workspace 4.2 的 WS-QUANTUM-999 如何恢复？"
    )


def test_synthetic_manifest_checksums_and_golden_set():
    base = ROOT / "assignments/final_capstone/yangong"
    manifest = json.loads((base / "data/manifest_webhook_troubleshooting.json").read_text())
    assert manifest["license_tag"] == "course_synthetic"
    assert manifest["pii_policy"]["scan_status"] == "clear"
    for asset in manifest["assets"]:
        path = ROOT / asset["source_url_or_path"]
        assert path.stat().st_size == asset["size_bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset["checksum_sha256"]

    cases = [
        json.loads(line)
        for line in (base / "evals/golden_set.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert [item["case_id"][:2] for item in cases] == [f"C{i}" for i in range(1, 9)]
    assert all(item["expected_action"]["control"] in {"none", "confirm", "hitl"} for item in cases)


def test_model_bundle_and_solution_card_are_wired_without_secrets():
    compose = (ROOT / "infra/docker-compose.yml").read_text()
    assert "Qwen/Qwen3-Embedding-4B" not in compose
    for variable in (
        "SILICONFLOW_API_KEY",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_DIMENSIONS",
        "RERANK_MODEL",
    ):
        assert variable in compose
    assert "llm.txt" in (ROOT / ".gitignore").read_text()
    assert "support_solution_card" in (
        ROOT / "infra/migrations/016_final_capstone_solution_card.sql"
    ).read_text()
