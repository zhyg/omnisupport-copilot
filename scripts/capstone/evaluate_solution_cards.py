"""Run the final-capstone Golden Set through the Product API."""

from __future__ import annotations

import argparse
import json
import math
import time
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
    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout) as client:
        token = _login(client, args.agent_email, args.agent_password)
        ticket_id = _workspace_case(client, token)
        for case in cases:
            started = time.perf_counter()
            response = _request(
                client,
                token,
                "POST",
                f"/api/v1/cases/{ticket_id}/solution-card",
                json={"question": case["question"], "retrieval_mode": case["expected_route"]},
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            latencies.append(latency_ms)
            card = response.json()
            text = "\n".join([card["summary"], *card["steps"]])
            sources = [citation["source"] for citation in card["citations"]]
            checks = {
                "release": card["release_id"] == args.expected_release_id,
                "identifiers": bool(card["abstain_reason"])
                or all(value.lower() in text.lower() for value in case["required_identifiers"]),
                "evidence": all(
                    any(_evidence_slug(value) in source for source in sources)
                    for value in case["required_evidence"]
                ),
                "abstain": bool(card["abstain_reason"]) == bool(case["expect_abstain"]),
                "clarification": bool(card["needs_clarification"])
                == bool(case["expect_clarification"]),
                "action": card["proposed_action"] == case["expected_action"],
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
                }
            )
    passed = sum(item["status"] == "pass" for item in results)
    return {
        "status": "pass" if passed == len(results) else "fail",
        "dataset": str(args.golden_set),
        "expected_release_id": args.expected_release_id,
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
            "latency_p50_ms": _percentile(latencies, 0.50),
            "latency_p95_ms": _percentile(latencies, 0.95),
        },
        "cases": results,
        "limitations": [
            "C7 fault injection is evidenced by the separate degraded-mode E2E report.",
            "C8 release rollback is evidenced by the release report and post-rollback E2E.",
            "Citation support is a deterministic required-source proxy, not an LLM judge.",
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
    parser.add_argument("--case-id", help="Run only a case-id prefix such as C4")
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
