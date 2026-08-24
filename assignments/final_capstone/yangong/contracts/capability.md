# Webhook troubleshooting solution-card capability

Version: solution-card-v1

## Purpose

Convert a tenant-scoped support question and released Webhook evidence into a
machine-valid problem-resolution card. The capability is advisory.

## Interface

- Product input: ticket ID, question and retrieval mode.
- Product output: contracts/product/solution_card.schema.json.
- Authentication: Product API user token; internal RAG calls require the
  service token and forward actor, role and tenant headers.
- Failure: missing evidence abstains; ambiguous Webhook context requests
  clarification; LLM, embedding or rerank failure falls back without inventing
  citations.
- Actions: add_internal_note requires explicit confirmation;
  grant_service_credit requires HITL. Generating a card performs no write other
  than storing the card and its audit record.
