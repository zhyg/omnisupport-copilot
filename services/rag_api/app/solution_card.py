"""Strict, evidence-bound solution-card generation and policy controls."""

from __future__ import annotations

import re
from typing import Iterable

from app.models.rag_models import (
    ProposedAction,
    RagAnswerResponse,
    SolutionCardCitation,
    SolutionCardResponse,
)

_IDENTIFIER = re.compile(
    r"(?:WS-[A-Z]+-[0-9]{3}|HTTP\s*[0-9]{3}|\bv?[0-9]+\.[0-9]+(?:\.[0-9]+)?\b)",
    re.IGNORECASE,
)


def needs_clarification(question: str, *, has_evidence: bool) -> bool:
    """Require a concrete error/status/version for ambiguous webhook reports."""

    lowered = question.lower()
    return bool(
        has_evidence
        and ("webhook" in lowered or "回调" in lowered)
        and not _IDENTIFIER.search(question)
    )


def proposed_action_for(question: str, *, abstain_reason: str | None) -> ProposedAction:
    """Server-side policy; model output can never select or execute an action."""

    if abstain_reason:
        return ProposedAction(operation="none", control="none")
    lowered = question.lower()
    if any(term in lowered for term in ("service credit", "credit", "refund", "补偿", "额度")):
        return ProposedAction(operation="grant_service_credit", control="hitl")
    if any(term in lowered for term in ("internal note", "add note", "备注", "内部记录")):
        return ProposedAction(operation="add_internal_note", control="confirm")
    return ProposedAction(operation="none", control="none")


def _sentences(value: str) -> Iterable[str]:
    for item in re.split(r"(?:\r?\n)+|(?<=[。！？.!?])\s+", value):
        cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)、])\s*", "", item).strip()
        if cleaned:
            yield cleaned


def deterministic_content(answer: str) -> tuple[str, list[str]]:
    """Auditable fallback that summarizes only the already-grounded answer."""

    parts = list(_sentences(answer))
    if not parts:
        return "当前没有可用的证据化处理方案。", []
    summary = parts[0][:2000]
    steps = [part[:1000] for part in parts[1:4]]
    if not steps and len(parts[0]) > 120:
        steps = [parts[0][:1000]]
    return summary, steps


async def build_solution_card(
    question: str,
    answer: RagAnswerResponse,
) -> tuple[SolutionCardResponse, dict[str, object]]:
    citations = [
        SolutionCardCitation(
            evidence_id=item.evidence_id,
            source=item.source_url or item.source_id,
        )
        for item in answer.citations
    ]
    clarify = needs_clarification(question, has_evidence=bool(citations))
    abstain_reason = answer.abstain_reason
    if clarify and not abstain_reason:
        abstain_reason = "missing_required_context"

    summary, steps = deterministic_content(answer.answer)
    # The answer itself may be LLM-generated, but the product contract is a
    # deterministic projection. This removes a second model call, prevents the
    # model from inventing fields/actions/citations, and bounds endpoint latency.
    generation: dict[str, object] = {
        "mode": "grounded_projection",
        "provider": answer.generation_provider,
        "model": answer.generation_model,
    }
    card = SolutionCardResponse(
        summary=summary,
        steps=steps[:3],
        citations=citations,
        confidence=answer.confidence,
        needs_clarification=clarify,
        abstain_reason=abstain_reason,
        proposed_action=proposed_action_for(question, abstain_reason=abstain_reason),
        release_id=answer.release_id,
        trace_id=answer.trace_id,
    )
    return card, generation
