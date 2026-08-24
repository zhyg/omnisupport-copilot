"""Verify the product control plane through its public HTTP APIs.

The verifier intentionally exercises real persistence and one approved service
credit. Re-running it is safe because every write uses a unique idempotency key.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from observability.week12.verify_phoenix import fetch_trace
from pipelines.query.rewriter import extract_protected_terms


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _trace_has(
    *, base_url: str, project: str, trace_id: str, required: set[str], retries: int = 15
) -> dict[str, Any]:
    trace = None
    names: set[str] = set()
    for _ in range(retries):
        trace = fetch_trace(base_url, project, trace_id)
        names = {span["name"] for span in trace.get("spans", [])} if trace else set()
        if required.issubset(names):
            break
        time.sleep(1)
    missing = sorted(required - names)
    _check(trace is not None, f"trace not found in Phoenix: {trace_id}")
    _check(not missing, f"trace {trace_id} is missing spans: {', '.join(missing)}")
    return {"trace_id": trace_id, "span_count": len(names), "required_spans": sorted(required)}


def _login(client: httpx.Client, email: str, password: str) -> tuple[str, dict[str, Any]]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    body = response.json()
    return body["access_token"], body["user"]


def _request(
    client: httpx.Client,
    token: str,
    method: str,
    path: str,
    **kwargs: Any,
) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = f"Bearer {token}"
    response = client.request(method, path, headers=headers, **kwargs)
    response.raise_for_status()
    return response


def _select_workspace_case(client: httpx.Client, token: str) -> dict[str, Any]:
    items = _request(client, token, "GET", "/api/v1/cases?limit=100").json()["items"]
    for item in items:
        detail = _request(client, token, "GET", f"/api/v1/cases/{item['ticket_id']}").json()["case"]
        if detail["product_line"] == "northstar_workspace":
            return detail
    raise RuntimeError("no northstar_workspace case found")


def run(args: argparse.Namespace) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    report: dict[str, Any] = {
        "status": "running",
        "run_id": run_id,
        "scenario": args.scenario,
        "checks": {},
    }
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=60.0) as client:
        live = client.get("/live")
        live.raise_for_status()
        ready = client.get("/health")
        ready.raise_for_status()
        _check(ready.json()["status"] == "ok", "product dependencies are degraded")
        if args.expected_release_id:
            _check(
                ready.json()["release_id"] == args.expected_release_id,
                "runtime release does not match the expected release",
            )
        report["checks"]["runtime"] = ready.json()

        agent_token, agent = _login(client, args.agent_email, args.agent_password)
        admin_token, admin = _login(client, args.admin_email, args.admin_password)
        _check(agent["tenant_id"] == admin["tenant_id"], "demo users are in different tenants")
        report["checks"]["identity"] = {
            "tenant_id": agent["tenant_id"],
            "agent_role": agent["role"],
            "admin_role": admin["role"],
        }

        case = _select_workspace_case(client, agent_token)
        _check(case["tenant_id"] == agent["tenant_id"], "case escaped tenant boundary")
        report["checks"]["case_queue"] = {
            "ticket_id": case["ticket_id"],
            "product_line": case["product_line"],
        }

        conversation = _request(
            client,
            agent_token,
            "POST",
            f"/api/v1/cases/{case['ticket_id']}/conversations",
            json={"title": f"Capstone E2E {run_id}"},
        ).json()
        answer_question = (
            "Workspace 4.2 的 Webhook 返回 HTTP 401 和 WS-WEBHOOK-401，"
            "在模型超时前后应如何排查？"
        )
        answer_response = _request(
            client,
            agent_token,
            "POST",
            f"/api/v1/conversations/{conversation['conversation_id']}/messages",
            json={
                "question": answer_question,
                "retrieval_mode": "hybrid",
                "include_debug": True,
            },
        )
        answer = answer_response.json()
        _check(answer["evidence_ids"], "RAG answer has no evidence")
        if args.require_llm:
            _check(answer.get("generation_mode") == "llm", "answer used deterministic fallback")
        if args.expected_generation_mode:
            _check(
                answer.get("generation_mode") == args.expected_generation_mode,
                "answer generation mode does not match the injected scenario",
            )
        _check(
            any("webhook" in str(item.get("source_url", "")) for item in answer["citations"]),
            "RAG did not retrieve a capstone webhook source",
        )
        rewrite_debug = answer.get("query_rewrite_debug") or {}
        expected_protected_terms = extract_protected_terms(answer_question)
        protected_terms_preserved = (
            rewrite_debug.get("lexical_term_count") == len(expected_protected_terms)
            and "preserve_lexical_identifiers" in rewrite_debug.get("rewrite_reasons", [])
            and not any(
                str(value).startswith(("restored_missing:", "removed_invented:"))
                for value in rewrite_debug.get("safety_repairs", [])
            )
        )
        if args.scenario == "llm_fault":
            _check(rewrite_debug.get("mode") == "fallback", "query rewrite did not fall back")
            _check(bool(rewrite_debug.get("fallback_reason")), "query rewrite fallback reason missing")
            _check(protected_terms_preserved, "query rewrite did not preserve protected identifiers")
        answer_text = str(answer.get("content") or answer.get("answer") or "")
        report["checks"]["rag"] = {
            "message_id": answer["message_id"],
            "trace_id": answer["trace_id"],
            "confidence": answer["confidence"],
            "evidence_count": len(answer["evidence_ids"]),
            "release_id": answer["release_id"],
            "generation_mode": answer.get("generation_mode"),
            "generation_provider": answer.get("generation_provider"),
            "generation_model": answer.get("generation_model"),
            "generation_fallback_reason": answer.get("generation_fallback_reason"),
            "output_character_count": len(answer_text),
            "estimated_output_tokens_proxy": math.ceil(len(answer_text) / 4),
            "query_rewrite_debug": {
                **rewrite_debug,
                "expected_protected_term_count": len(expected_protected_terms),
                "protected_terms_preserved": protected_terms_preserved,
            },
        }
        card_path = f"/api/v1/cases/{case['ticket_id']}/solution-card"
        card_request = {
            "question": (
                "Workspace 4.2 的 Webhook 返回 HTTP 401 和 "
                "WS-WEBHOOK-401，应该如何排查？"
            ),
            "retrieval_mode": "hybrid",
        }
        if args.expect_solution_card_disabled:
            card_response = client.post(
                card_path,
                headers={"Authorization": f"Bearer {agent_token}"},
                json=card_request,
            )
            _check(card_response.status_code == 404, "rollback left solution-card enabled")
            _check(
                card_response.json().get("detail") == "solution_card_disabled",
                "solution-card failed for a reason other than the rollback feature gate",
            )
            report["checks"]["solution_card_disabled"] = {
                "status_code": card_response.status_code,
                "detail": card_response.json()["detail"],
            }
        else:
            card_response = _request(
                client,
                agent_token,
                "POST",
                card_path,
                json=card_request,
            )
            card = card_response.json()
            expected_card_fields = {
                "summary",
                "steps",
                "citations",
                "confidence",
                "needs_clarification",
                "abstain_reason",
                "proposed_action",
                "release_id",
                "trace_id",
            }
            _check(set(card) == expected_card_fields, "solution card contract fields changed")
            _check(len(card["steps"]) <= 3, "solution card returned more than three steps")
            _check(card["citations"], "solution card has no evidence")
            _check(not card["needs_clarification"], "precise solution-card query was marked ambiguous")
            _check(card["abstain_reason"] is None, "grounded solution card abstained")
            _check(
                card["proposed_action"] == {"operation": "none", "control": "none"},
                "solution card proposed an uncontrolled action",
            )
            report["checks"]["solution_card"] = {
                "trace_id": card["trace_id"],
                "release_id": card["release_id"],
                "confidence": card["confidence"],
                "step_count": len(card["steps"]),
                "evidence_ids": [item["evidence_id"] for item in card["citations"]],
                "response_fields": sorted(card),
            }
        _request(
            client,
            agent_token,
            "POST",
            f"/api/v1/messages/{answer['message_id']}/feedback",
            json={"rating": 1, "reason_code": "e2e_verified", "comment": "Automated capstone verification"},
        )
        report["checks"]["feedback"] = {"status": "persisted"}

        overview = _request(client, agent_token, "GET", "/api/v1/operations/overview").json()
        if args.expected_release_id:
            _check(
                overview.get("release", {}).get("release_id") == args.expected_release_id,
                "active release pointer does not match the expected release",
            )
        report["checks"]["release_pointer"] = overview.get("release")
        date_to = date.fromisoformat(overview["data_window"]["date_to"])
        available_from = date.fromisoformat(overview["data_window"]["date_from"])
        date_from = max(available_from, date_to - timedelta(days=30))
        kpi = _request(
            client,
            agent_token,
            "POST",
            "/api/v1/analytics/kpis",
            json={
                "metrics": ["ticket_count", "sla_breach_count"],
                "dimensions": ["product_line"],
                "filters": {},
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "limit": 100,
            },
        ).json()
        _check(kpi["allowed"] and kpi["rows"], "governed KPI query returned no rows")
        _check("semantic_aggregation" in kpi["policy_applied"], "semantic aggregation policy missing")
        report["checks"]["kpi"] = {
            "row_count": len(kpi["rows"]),
            "audit_id": kpi["audit_id"],
            "policies": kpi["policy_applied"],
        }

        note_reason = f"Capstone E2E evidence review completed ({run_id})."
        note_key = f"capstone-e2e-note-{run_id}"
        before_note = _request(
            client, agent_token, "GET", f"/api/v1/cases/{case['ticket_id']}"
        ).json()
        note_payload = {
            "operation": "add_internal_note",
            "reason": note_reason,
            "evidence_ids": answer["evidence_ids"],
            "idempotency_key": note_key,
        }
        note = _request(
            client,
            agent_token,
            "POST",
            f"/api/v1/cases/{case['ticket_id']}/actions",
            json=note_payload,
        ).json()
        _check(note["status"] == "completed", "low-risk ticket action did not complete")
        note_replay = _request(
            client,
            agent_token,
            "POST",
            f"/api/v1/cases/{case['ticket_id']}/actions",
            json=note_payload,
        ).json()
        after_note = _request(
            client, agent_token, "GET", f"/api/v1/cases/{case['ticket_id']}"
        ).json()
        before_count = sum(item.get("body") == note_reason for item in before_note.get("comments", []))
        after_count = sum(item.get("body") == note_reason for item in after_note.get("comments", []))
        _check(note_replay["status"] == "cached", "idempotent action replay was not cached")
        _check(
            note_replay.get("lineage_event_id") == note.get("lineage_event_id"),
            "idempotent replay created a second lineage event",
        )
        _check(
            before_count == 0 and after_count == 1,
            "idempotent replay duplicated the ticket timeline side effect",
        )
        report["checks"]["low_risk_action"] = {
            "idempotency_key": note_key,
            "first": note,
            "replay": note_replay,
            "timeline_before_count": before_count,
            "timeline_after_count": after_count,
        }

        credit_response = _request(
            client,
            agent_token,
            "POST",
            f"/api/v1/cases/{case['ticket_id']}/actions",
            json={
                "operation": "grant_service_credit",
                "reason": f"Capstone E2E verifies financial HITL ({run_id}).",
                "amount_cents": 100,
                "currency": "USD",
                "evidence_ids": answer["evidence_ids"],
                "idempotency_key": f"capstone-e2e-credit-{run_id}",
            },
        )
        credit = credit_response.json()
        _check(credit["status"] == "awaiting_approval", "financial action bypassed HITL")
        approval_response = _request(
            client,
            admin_token,
            "POST",
            f"/api/v1/approvals/{credit['approval_id']}/decision",
            json={"approved": True, "reason": "Automated E2E: evidence and one-dollar limit verified"},
        )
        approval = approval_response.json()
        _check(approval["status"] == "completed", "approved action did not resume")
        report["checks"]["hitl"] = {
            "approval_id": credit["approval_id"],
            "wait_trace_id": credit_response.headers.get("X-Trace-ID"),
            "resume_trace_id": approval_response.headers.get("X-Trace-ID"),
            "status": approval["status"],
        }

    if not args.skip_phoenix:
        report["checks"]["phoenix_rag"] = _trace_has(
            base_url=args.phoenix_url,
            project=args.phoenix_project,
            trace_id=report["checks"]["rag"]["trace_id"],
            required={"product.copilot.answer", "rag.query", "rag.retrieve.hybrid", "rag.audit.persist"},
        )
        if not args.expect_solution_card_disabled:
            report["checks"]["phoenix_solution_card"] = _trace_has(
                base_url=args.phoenix_url,
                project=args.phoenix_project,
                trace_id=report["checks"]["solution_card"]["trace_id"],
                required={
                    "product.solution_card",
                    "rag.solution_card",
                    "rag.query",
                    "rag.retrieve.hybrid",
                },
            )
        report["checks"]["phoenix_hitl_wait"] = _trace_has(
            base_url=args.phoenix_url,
            project=args.phoenix_project,
            trace_id=report["checks"]["hitl"]["wait_trace_id"],
            required={"hitl.evaluate", "hitl.wait", "agent.lineage.persist"},
        )
        report["checks"]["phoenix_hitl_resume"] = _trace_has(
            base_url=args.phoenix_url,
            project=args.phoenix_project,
            trace_id=report["checks"]["hitl"]["resume_trace_id"],
            required={"hitl.resume", "tool.execute.ticket_update", "agent.lineage.persist"},
        )

    report["status"] = "pass"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the enterprise capstone product E2E")
    parser.add_argument("--base-url", default="http://copilot_api:8002")
    parser.add_argument("--phoenix-url", default="http://phoenix:6006")
    parser.add_argument("--phoenix-project", default="omnisupport-copilot")
    parser.add_argument("--agent-email", default="agent@northstar.demo")
    parser.add_argument("--agent-password", default="Agent@2026")
    parser.add_argument("--admin-email", default="admin@northstar.demo")
    parser.add_argument("--admin-password", default="Admin@2026")
    parser.add_argument("--output", default="reports/capstone/e2e-verification.json")
    parser.add_argument("--skip-phoenix", action="store_true")
    parser.add_argument(
        "--scenario",
        choices=("standard", "baseline_legacy", "llm_fault", "release_rollback"),
        default="standard",
    )
    parser.add_argument("--expected-release-id")
    parser.add_argument(
        "--expected-generation-mode",
        choices=("llm", "deterministic_fallback"),
    )
    parser.add_argument("--expect-solution-card-disabled", action="store_true")
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Fail unless the product answer was generated by a configured LLM provider",
    )
    args = parser.parse_args()
    try:
        if args.scenario == "llm_fault":
            _check(
                args.expected_generation_mode == "deterministic_fallback",
                "llm_fault requires --expected-generation-mode deterministic_fallback",
            )
        if args.scenario in {"baseline_legacy", "release_rollback"}:
            _check(bool(args.expected_release_id), "release_rollback requires --expected-release-id")
            _check(
                args.expect_solution_card_disabled,
                f"{args.scenario} requires --expect-solution-card-disabled",
            )
        report = run(args)
    except Exception as exc:
        report = {"status": "fail", "error": str(exc), "error_type": type(exc).__name__}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
