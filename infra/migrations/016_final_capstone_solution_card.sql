-- Final Capstone: persisted, tenant-scoped structured solution cards.

CREATE TABLE IF NOT EXISTS support_solution_card (
    card_id             TEXT PRIMARY KEY,
    tenant_id           TEXT NOT NULL,
    ticket_id           TEXT NOT NULL REFERENCES ticket_fact(ticket_id),
    actor_id            TEXT NOT NULL REFERENCES app_user(user_id),
    question            TEXT NOT NULL,
    card                JSONB NOT NULL,
    evidence_ids        TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    trace_id            TEXT NOT NULL,
    release_id          TEXT NOT NULL,
    generation_mode     TEXT,
    generation_provider TEXT,
    generation_model    TEXT,
    latency_ms          INTEGER NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_solution_card_case_latest
    ON support_solution_card (tenant_id, ticket_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_solution_card_trace
    ON support_solution_card (trace_id);
