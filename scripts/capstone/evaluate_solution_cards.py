"""Run the final-capstone Golden Set through the Product API."""

from __future__ import annotations

import argparse
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any

import httpx


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 2)


def _login(client: httpx.Client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return str(response.json()["access_token"])


def _request(client: httpx.Client, token: str, method: str, path: str, **kwargs: Any) -> httpx.Response:
    response = client.request(
        method,
        path,
        headers={"Authorization": f"Bearer {token}"},
        **kwargs,
    )
    response.raise_for_status()
    return response


def _workspace_case(client: httpx.Client, token: str) -> str:
    items = _request(client, token, "GET", "/api/v1/cases?limit=100").json()["items"]
    for item in items:
        ticket_id = item["ticket_id"]
        detail = _request(client, token, "GET", f"/api/v1/cases/{ticket_id}").json()["case"]
        if detail["product_line"] == "northstar_workspace":
            return str(ticket_id)
    raise RuntimeError("no northstar_workspace case found")


def _evidence_slug(value: str) -> str:
    return value.rsplit(":", 1)[-1]


def _citation_slug(value: str) -> str:
    normalized = value.split("?", 1)[0].rstrip("/")
    leaf = normalized.rsplit("/", 1)[-1]
    return _evidence_slug(leaf).removesuffix(".html")


def _citations_supported(
    citations: list[dict[str, Any]],
    *,
    required_evidence: list[str],
    allowed_evidence: list[str] | None = None,
) -> bool:
    """Require every mandatory source and reject citations outside the allow-list."""

    required = {_evidence_slug(value) for value in required_evidence}
    allowed = {
        _evidence_slug(value)
        for value in (allowed_evidence if allowed_evidence is not None else required_evidence)
    }
    observed_slugs = {_citation_slug(str(item.get("source", ""))) for item in citations}
    every_citation_allowed = observed_slugs.issubset(allowed)
    return required.issubset(observed_slugs) and every_citation_allowed


def _load_report(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario_result(
    case: dict[str, Any],
    *,
    fault_report: dict[str, Any] | None,
    rollback_report: dict[str, Any] | None,
    rollback_manifest: dict[str, Any] | None,
    expected_release_id: str,
    expected_rollback_release_id: str | None,
) -> dict[str, Any] | None:
    if case.get("fault_injection"):
        report = fault_report or {}
        checks = report.get("checks", {})
        runtime = checks.get("runtime", {})
        rag = checks.get("rag", {})
        pointer = checks.get("release_pointer", {}) or {}
        rewrite = rag.get("query_rewrite_debug", {}) or {}
        validation = {
            "scenario_setup": report.get("scenario") == "llm_fault",
            "service_healthy": report.get("status") == "pass"
            and runtime.get("status") == "ok",
            "release": runtime.get("release_id") == expected_release_id
            and rag.get("release_id") == expected_release_id
            and pointer.get("release_id") == expected_release_id,
            "fallback": rag.get("generation_mode") == "deterministic_fallback",
            "fallback_reason": bool(rag.get("generation_fallback_reason")),
            "rewrite_fallback": rewrite.get("mode") == "fallback",
            "rewrite_fallback_reason": bool(rewrite.get("fallback_reason")),
            "rewrite_identifiers": rewrite.get("protected_terms_preserved") is True
            and int(rewrite.get("lexical_term_count", 0)) > 0,
            "evidence": int(rag.get("evidence_count", 0)) > 0,
            "contract": bool(rag.get("trace_id")),
        }
        return {
            "case_id": case["case_id"],
            "status": "pass" if all(validation.values()) else "not_run",
            "checks": validation,
            "latency_ms": None,
            "trace_id": rag.get("trace_id"),
            "release_id": rag.get("release_id"),
            "confidence": rag.get("confidence"),
            "abstain_reason": None,
            "needs_clarification": False,
            "proposed_action": {"operation": "none", "control": "none"},
            "evidence_ids": [],
            "sources": [],
        }
    if case.get("requires_release_rollback"):
        report = rollback_report or {}
        checks = report.get("checks", {})
        runtime = checks.get("runtime", {})
        rag = checks.get("rag", {})
        disabled = checks.get("solution_card_disabled", {})
        pointer = checks.get("release_pointer", {}) or {}
        manifest = rollback_manifest or {}
        manifest_components = manifest.get("spec", {}).get("components", {})
        expected_components = {
            name: manifest_components.get(name, {}).get("release_id")
            for name in ("data", "index", "prompt", "graph")
        }
        observed_components = {
            name: pointer.get(f"{name}_release_id")
            for name in ("data", "index", "prompt", "graph")
        }
        validation = {
            "scenario_setup": report.get("scenario") == "release_rollback",
            "legacy_e2e": report.get("status") == "pass" and runtime.get("status") == "ok",
            "release": bool(expected_rollback_release_id)
            and runtime.get("release_id") == expected_rollback_release_id
            and rag.get("release_id") == expected_rollback_release_id
            and pointer.get("release_id") == expected_rollback_release_id,
            "new_capability_disabled": disabled
            == {"status_code": 404, "detail": "solution_card_disabled"},
            "component_bindings": bool(rollback_manifest)
            and manifest.get("metadata", {}).get("release_id")
            == expected_rollback_release_id
            and expected_components == observed_components
            and manifest_components.get("service", {})
            .get("feature_flags", {})
            .get("solution_card")
            is False,
            "evidence": int(rag.get("evidence_count", 0)) > 0,
            "contract": bool(rag.get("trace_id")),
        }
        return {
            "case_id": case["case_id"],
            "status": "pass" if all(validation.values()) else "not_run",
            "checks": validation,
            "latency_ms": None,
            "trace_id": rag.get("trace_id"),
            "release_id": rag.get("release_id"),
            "confidence": rag.get("confidence"),
            "abstain_reason": None,
            "needs_clarification": False,
            "proposed_action": {"operation": "none", "control": "none"},
            "evidence_ids": [],
            "sources": [],
        }
    return None


def run(args: argparse.Namespace) -> dict[str, Any]:
    cases = [
        json.loads(line)
        for line in args.golden_set.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.case_id:
        cases = [case for case in cases if case["case_id"].startswith(args.case_id)]
        if not cases:
            raise ValueError(f"unknown case_id prefix: {args.case_id}")
    if args.exclude_case_id:
        cases = [
            case
            for case in cases
            if not any(
                case["case_id"].startswith(prefix) for prefix in args.exclude_case_id
            )
        ]
        if not cases:
            raise ValueError("case filters removed the entire Golden Set")
    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    fault_report = _load_report(args.fault_report)
    rollback_report = _load_report(args.rollback_report)
    rollback_manifest = _load_report(args.rollback_manifest)
    environment: dict[str, Any] = {}
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout) as client:
        runtime = client.get("/health")
        runtime.raise_for_status()
        runtime_payload = runtime.json()
        token = _login(client, args.agent_email, args.agent_password)
        pointer = _request(client, token, "GET", "/api/v1/operations/overview").json().get(
            "release", {}
        ) or {}
        environment = {"runtime": runtime_payload, "release_pointer": pointer}
        environment_release_matches = (
            runtime_payload.get("release_id") == args.expected_release_id
            and pointer.get("release_id") == args.expected_release_id
        )
        ticket_id = _workspace_case(client, token)
        for case in cases:
            scenario = None
            if not args.expect_solution_card_disabled:
                scenario = _scenario_result(
                    case,
                    fault_report=fault_report,
                    rollback_report=rollback_report,
                    rollback_manifest=rollback_manifest,
                    expected_release_id=args.expected_release_id,
                    expected_rollback_release_id=args.expected_rollback_release_id,
                )
            if scenario is not None:
                results.append(scenario)
                continue
            started = time.perf_counter()
            response = client.post(
                f"/api/v1/cases/{ticket_id}/solution-card",
                headers={"Authorization": f"Bearer {token}"},
                json={"question": case["question"], "retrieval_mode": case["expected_route"]},
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            latencies.append(latency_ms)
            if args.expect_solution_card_disabled:
                body = response.json()
                disabled = response.status_code == 404 and body.get("detail") == "solution_card_disabled"
                results.append(
                    {
                        "case_id": case["case_id"],
                        "status": "fail",
                        "checks": {
                            "release": environment_release_matches,
                            "identifiers": False,
                            "evidence": False,
                            "abstain": False,
                            "clarification": False,
                            "action": False,
                            "action_replay": False,
                            "contract": False,
                            "baseline_endpoint_disabled": disabled,
                        },
                        "latency_ms": latency_ms,
                        "http_status": response.status_code,
                        "response": body,
                        "trace_id": None,
                        "release_id": args.expected_release_id,
                        "confidence": None,
                        "abstain_reason": None,
                        "needs_clarification": False,
                        "proposed_action": {"operation": "none", "control": "none"},
                        "evidence_ids": [],
                        "sources": [],
                    }
                )
                continue
            response.raise_for_status()
            card = response.json()
            text = "\n".join([card["summary"], *card["steps"]])
            sources = [citation["source"] for citation in card["citations"]]
            action_replay: dict[str, Any] | None = None
            if case["expected_action"] == {"operation": "add_internal_note", "control": "confirm"}:
                reason = f"Golden C5 idempotency replay verification ({uuid.uuid4().hex})."
                idempotency_key = f"golden-c5-{uuid.uuid4().hex}"
                before = _request(client, token, "GET", f"/api/v1/cases/{ticket_id}").json()
                action_payload = {
                    "operation": "add_internal_note",
                    "reason": reason,
                    "evidence_ids": [item["evidence_id"] for item in card["citations"]],
                    "idempotency_key": idempotency_key,
                }
                first = _request(
                    client, token, "POST", f"/api/v1/cases/{ticket_id}/actions", json=action_payload
                ).json()
                replay = _request(
                    client, token, "POST", f"/api/v1/cases/{ticket_id}/actions", json=action_payload
                ).json()
                after = _request(client, token, "GET", f"/api/v1/cases/{ticket_id}").json()
                before_count = sum(item.get("body") == reason for item in before.get("comments", []))
                after_count = sum(item.get("body") == reason for item in after.get("comments", []))
                action_replay = {
                    "idempotency_key": idempotency_key,
                    "first": first,
                    "replay": replay,
                    "timeline_before_count": before_count,
                    "timeline_after_count": after_count,
                    "passed": first.get("status") == "completed"
                    and replay.get("status") == "cached"
                    and bool(first.get("lineage_event_id"))
                    and replay.get("lineage_event_id") == first.get("lineage_event_id")
                    and before_count == 0
                    and after_count == 1,
                }
            checks = {
                "release": card["release_id"] == args.expected_release_id,
                "identifiers": bool(card["abstain_reason"])
                or all(value.lower() in text.lower() for value in case["required_identifiers"]),
                "evidence": _citations_supported(
                    card["citations"],
                    required_evidence=case["required_evidence"],
                    allowed_evidence=case.get("allowed_evidence"),
                ),
                "abstain": bool(card["abstain_reason"]) == bool(case["expect_abstain"]),
                "clarification": bool(card["needs_clarification"])
                == bool(case["expect_clarification"]),
                "action": card["proposed_action"] == case["expected_action"],
                "action_replay": action_replay is None or action_replay["passed"],
                "contract": len(card["steps"]) <= 3 and bool(card["trace_id"]),
            }
            results.append(
                {
                    "case_id": case["case_id"],
                    "status": "pass" if all(checks.values()) else "fail",
                    "checks": checks,
                    "latency_ms": latency_ms,
                    "trace_id": card["trace_id"],
                    "release_id": card["release_id"],
                    "confidence": card["confidence"],
                    "abstain_reason": card["abstain_reason"],
                    "needs_clarification": card["needs_clarification"],
                    "proposed_action": card["proposed_action"],
                    "evidence_ids": [item["evidence_id"] for item in card["citations"]],
                    "sources": sources,
                    "output_character_count": len(text),
                    "estimated_output_tokens_proxy": math.ceil(len(text) / 4),
                    "action_replay": action_replay,
                }
            )
    passed = sum(item["status"] == "pass" for item in results)
    measured_outputs = [item for item in results if "output_character_count" in item]
    return {
        "status": "pass" if passed == len(results) else "fail",
        "dataset": str(args.golden_set),
        "expected_release_id": args.expected_release_id,
        "environment": environment,
        "case_count": len(results),
        "passed": passed,
        "metrics": {
            "key_point_pass_rate": round(passed / len(results), 4),
            "citation_support_proxy_rate": round(
                sum(item["checks"]["evidence"] for item in results) / len(results), 4
            ),
            "unsafe_action_bypass_count": sum(
                item["proposed_action"]["control"] == "none"
                and item["proposed_action"]["operation"] != "none"
                for item in results
            ),
            "latency_p50_ms": _percentile(latencies, 0.50) if latencies else None,
            "latency_p95_ms": _percentile(latencies, 0.95) if latencies else None,
            "average_output_characters": round(
                sum(item["output_character_count"] for item in measured_outputs)
                / len(measured_outputs),
                2,
            ) if measured_outputs else None,
            "average_estimated_output_tokens_proxy": round(
                sum(item["estimated_output_tokens_proxy"] for item in measured_outputs)
                / len(measured_outputs),
                2,
            ) if measured_outputs else None,
        },
        "cases": results,
        "limitations": [
            "C7/C8 only pass when their machine-readable scenario reports prove setup and outcome.",
            "Every returned citation must belong to the case allow-list and every required source must appear; this remains a source-level proxy, not a claim-entailment judge.",
            "Estimated output tokens use ceil(Unicode character count / 4) because the frozen product contract does not expose provider usage.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://copilot_api:8002")
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=Path("assignments/final_capstone/yangong/evals/golden_set.jsonl"),
    )
    parser.add_argument("--expected-release-id", required=True)
    parser.add_argument("--fault-report", type=Path)
    parser.add_argument("--rollback-report", type=Path)
    parser.add_argument("--rollback-manifest", type=Path)
    parser.add_argument("--expected-rollback-release-id")
    parser.add_argument(
        "--expect-solution-card-disabled",
        action="store_true",
        help="Run every Golden question against a pre-change endpoint expected to return 404.",
    )
    parser.add_argument("--case-id", help="Run only a case-id prefix such as C4")
    parser.add_argument(
        "--exclude-case-id",
        action="append",
        default=[],
        help="Exclude a case-id prefix; repeat for multiple cases",
    )
    parser.add_argument("--agent-email", default="agent@northstar.demo")
    parser.add_argument("--agent-password", default="Agent@2026")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/capstone/solution-card-eval.json"),
    )
    args = parser.parse_args()
    try:
        report = run(args)
    except Exception as exc:
        report = {"status": "fail", "error": str(exc), "error_type": type(exc).__name__}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
