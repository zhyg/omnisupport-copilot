from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_MANIFEST = (
    ROOT / "assignments/final_capstone/yangong/reports/releases/omni-dev-v2026.08.28-001.json"
)
sys.path.insert(0, str(ROOT / "services/rag_api"))

from app import retrieval  # noqa: E402
from app.models.rag_models import ProposedAction, SolutionCardResponse  # noqa: E402
from app.routers.rag import _debug_payload  # noqa: E402
from app.solution_card import needs_clarification, proposed_action_for  # noqa: E402

from pipelines.indexing.embedder import (  # noqa: E402
    _embedding_api_key,
    _embedding_base_url,
)
from pipelines.query.rewriter import extract_protected_terms  # noqa: E402
from release.integrity import iter_artifact_digests  # noqa: E402
from release.verify import verify_release_manifest  # noqa: E402
from scripts.capstone.evaluate_solution_cards import (  # noqa: E402
    _citations_supported,
    _scenario_result,
)
from scripts.capstone.generate_demo_data import generate_manifests  # noqa: E402
from services.graph.models import GraphEvidenceChunk  # noqa: E402


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
    manifest_schema = json.loads(
        (ROOT / "data/seed_manifests/source_manifest_schema.json").read_text()
    )
    jsonschema.Draft202012Validator(manifest_schema).validate(manifest)
    assert manifest["license_tag"] == "course_synthetic"
    assert manifest["contract_ref"] == "omni://contracts/data/doc_asset/v1"
    assert all(asset["pii_scan_status"] == "clear" for asset in manifest["assets"])
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


def test_generated_manifest_preserves_assignment_language_and_version_metadata(tmp_path):
    outputs = generate_manifests(root=ROOT, output_dir=tmp_path)
    workspace = json.loads(
        next(path for path in outputs if path.name == "manifest_northstar_workspace.json").read_text()
    )
    assignment_assets = {
        item["source_id"]: item
        for item in workspace["assets"]
        if item["source_id"].startswith("doc:capstone:webhook-")
    }
    assert set(assignment_assets) == {
        "doc:capstone:webhook-signature-rotation",
        "doc:capstone:webhook-retry-idempotency",
    }
    assert all(item["language"] == "zh-CN" for item in assignment_assets.values())
    assert all("文档版本 1.0" in item["notes"] for item in assignment_assets.values())


def test_embedding_credentials_are_provider_scoped(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "siliconflow-secret")
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)

    assert _embedding_api_key("openai", None) == "openai-secret"
    assert (
        _embedding_api_key("siliconflow", "https://api.siliconflow.cn/v1")
        == "siliconflow-secret"
    )
    assert _embedding_api_key("openai", "https://api.siliconflow.cn/v1") == ""
    assert _embedding_api_key("siliconflow", "https://api.openai.com/v1") == ""
    assert _embedding_base_url("siliconflow") == "https://api.siliconflow.cn/v1"


def test_rerank_never_falls_back_to_openai_credentials(monkeypatch):
    monkeypatch.setattr(retrieval.settings, "rerank_provider", "siliconflow")
    monkeypatch.setattr(retrieval.settings, "rerank_base_url", "https://api.siliconflow.cn/v1")
    monkeypatch.setattr(retrieval.settings, "rerank_api_key", "")
    monkeypatch.setattr(retrieval.settings, "siliconflow_api_key", "siliconflow-secret")
    monkeypatch.setattr(retrieval.settings, "openai_api_key", "openai-secret")
    assert retrieval._rerank_api_key() == "siliconflow-secret"

    monkeypatch.setattr(retrieval.settings, "siliconflow_api_key", "")
    assert retrieval._rerank_api_key() == ""

    monkeypatch.setattr(retrieval.settings, "rerank_base_url", "https://rerank.example.test/v1")
    monkeypatch.setattr(retrieval.settings, "siliconflow_api_key", "siliconflow-secret")
    assert retrieval._rerank_api_key() == ""


def test_graph_debug_uses_safe_rerank_defaults():
    chunk = GraphEvidenceChunk(
        chunk_id="chunk-1",
        evidence_id="evidence-1",
        doc_id="doc-1",
        source_id="source-1",
        content="graph evidence",
        section_path="root",
        final_score=0.9,
    )
    debug = _debug_payload([chunk], {}, mode="graph_multihop")
    assert debug.rerank_provider == "none"
    assert debug.rerank_model == "none"
    assert debug.rerank_latency_ms == 0.0


def test_operational_cases_cannot_pass_without_scenario_setup():
    c7 = {"case_id": "C7_model_failure", "fault_injection": "llm_timeout"}
    c8 = {"case_id": "C8_rollback", "requires_release_rollback": True}
    assert _scenario_result(
        c7,
        fault_report=None,
        rollback_report=None,
        rollback_manifest=None,
        expected_release_id="candidate",
        expected_rollback_release_id=None,
    )["status"] == "not_run"
    assert _scenario_result(
        c8,
        fault_report=None,
        rollback_report=None,
        rollback_manifest=None,
        expected_release_id="candidate",
        expected_rollback_release_id=None,
    )["status"] == "not_run"


def test_operational_cases_validate_fault_and_real_rollback_evidence():
    fault = {
        "status": "pass",
        "scenario": "llm_fault",
        "checks": {
            "runtime": {"status": "ok", "release_id": "candidate"},
            "release_pointer": {"release_id": "candidate"},
            "rag": {
                "generation_mode": "deterministic_fallback",
                "generation_fallback_reason": "llm_error:APITimeoutError",
                "evidence_count": 5,
                "trace_id": "trace-fault",
                "release_id": "candidate",
                "query_rewrite_debug": {
                    "mode": "fallback",
                    "fallback_reason": "llm_error:APITimeoutError",
                    "lexical_term_count": 2,
                    "protected_terms_preserved": True,
                },
            },
        },
    }
    rollback = {
        "status": "pass",
        "scenario": "release_rollback",
        "checks": {
            "runtime": {"status": "ok", "release_id": "baseline"},
            "release_pointer": {
                "release_id": "baseline",
                "data_release_id": "data-baseline",
                "index_release_id": "index-baseline",
                "prompt_release_id": "prompt-baseline",
                "graph_release_id": "graph-baseline",
            },
            "rag": {
                "release_id": "baseline",
                "evidence_count": 5,
                "trace_id": "trace-rollback",
            },
            "solution_card_disabled": {
                "status_code": 404,
                "detail": "solution_card_disabled",
            },
        },
    }
    assert _scenario_result(
        {"case_id": "C7", "fault_injection": "llm_timeout"},
        fault_report=fault,
        rollback_report=None,
        rollback_manifest=None,
        expected_release_id="candidate",
        expected_rollback_release_id=None,
    )["status"] == "pass"
    assert _scenario_result(
        {"case_id": "C8", "requires_release_rollback": True},
        fault_report=None,
        rollback_report=rollback,
        rollback_manifest={
            "metadata": {"release_id": "baseline"},
            "spec": {
                "components": {
                    "data": {"release_id": "data-baseline"},
                    "index": {"release_id": "index-baseline"},
                    "prompt": {"release_id": "prompt-baseline"},
                    "graph": {"release_id": "graph-baseline"},
                    "service": {"feature_flags": {"solution_card": False}},
                }
            },
        },
        expected_release_id="candidate",
        expected_rollback_release_id="baseline",
    )["status"] == "pass"


def test_fault_scenario_rejects_cross_release_and_missing_rewrite_evidence():
    report = {
        "status": "pass",
        "scenario": "llm_fault",
        "checks": {
            "runtime": {"status": "ok", "release_id": "old-release"},
            "release_pointer": {"release_id": "old-release"},
            "rag": {
                "release_id": "old-release",
                "generation_mode": "deterministic_fallback",
                "generation_fallback_reason": "llm_error:APITimeoutError",
                "evidence_count": 1,
                "trace_id": "trace-old",
            },
        },
    }
    result = _scenario_result(
        {"case_id": "C7", "fault_injection": "llm_timeout"},
        fault_report=report,
        rollback_report=None,
        rollback_manifest=None,
        expected_release_id="candidate",
        expected_rollback_release_id=None,
    )
    assert result["status"] == "not_run"
    assert result["checks"]["release"] is False
    assert result["checks"]["rewrite_fallback"] is False


def test_citation_support_rejects_extras_and_requires_empty_refusal_citations():
    required = ["doc:capstone:webhook-signature-rotation"]
    correct = [{"source": "/knowledge/webhook-signature-rotation.html"}]
    unrelated = {"source": "/knowledge/unrelated.html"}
    assert _citations_supported(correct, required_evidence=required)
    assert not _citations_supported([*correct, unrelated], required_evidence=required)
    assert not _citations_supported(
        [{"source": "/knowledge/webhook-signature-rotation-evil.html"}],
        required_evidence=required,
    )
    assert _citations_supported([], required_evidence=[])
    assert not _citations_supported([unrelated], required_evidence=[])


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
    product_api = (ROOT / "services/copilot_api/app/main.py").read_text()
    assert 'result["query_rewrite_debug"] = answer.get("query_rewrite_debug")' in product_api


def test_candidate_release_manifest_binds_the_current_tree_and_final_evidence():
    manifest = json.loads(CANDIDATE_MANIFEST.read_text())
    assert verify_release_manifest(manifest, project_root=ROOT) == []
    assert manifest["metadata"]["previous_release_id"] == "omni-dev-v2026.08.24-003"

    bound = {path for _, path, _ in iter_artifact_digests(manifest)}
    assert manifest["spec"]["quality"]["eval"]["report_path"] in bound
    for name in (
        "raw/solution-card-eval-candidate.json",
        "raw/solution-card-eval-baseline.json",
        "raw/e2e-candidate-final.json",
        "raw/bootstrap-replay.json",
        "services/rag_api/app/solution_card.py",
    ):
        assert any(path.endswith(name) for path in bound), name
    # The superseded pre-release evidence must not come back as a gate artifact.
    assert not any(path.endswith("raw/solution-card-eval-pre-release.json") for path in bound)
