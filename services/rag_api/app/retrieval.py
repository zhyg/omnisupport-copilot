"""Hybrid Retrieval — 向量检索 + FTS + Cross-Encoder Rerank

实现混合检索链路：
  1. pgvector ANN 向量检索（语义相似）
  2. PostgreSQL FTS 倒排检索（关键词精确）
  3. RRF (Reciprocal Rank Fusion) 合并两路结果
  4. Cross-Encoder Rerank 精排（可选）
  5. 回填完整 evidence_anchor 字段
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Sequence

import httpx

from app.config import settings
from observability.runtime import traced_span

logger = logging.getLogger(__name__)

FTS_STOPWORDS = {
    "a", "an", "and", "are", "before", "do", "does", "for", "from", "how", "i", "in",
    "is", "must", "of", "on", "or", "please", "the", "to", "what", "when", "with",
}


def _format_pgvector(vector: Sequence[float]) -> str:
    """Serialize a Python vector into pgvector's text input format."""

    return "[" + ",".join(f"{float(value):.9g}" for value in vector) + "]"


# ── 结果结构 ──────────────────────────────────────────────────────────────────

@dataclass
class RetrievalResult:
    chunk_id: str
    evidence_id: str
    doc_id: str
    source_id: str
    content: str
    section_path: str
    page_no: int | None
    title: str | None
    bbox: str | None
    source_url: str | None
    doc_version: str | None
    section_type: str
    data_release_id: str | None = None
    index_release_id: str | None = None

    vector_score: float = 0.0
    fts_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float | None = None
    rerank_provider: str = "none"
    rerank_model: str = "none"
    rerank_fallback_reason: str | None = None
    rerank_latency_ms: float = 0.0

    @property
    def final_score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else self.rrf_score

    def debug_scores(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "vector_score": self.vector_score,
            "fts_score": self.fts_score,
            "rrf_score": self.rrf_score,
            "rerank_score": self.rerank_score,
            "final_score": self.final_score,
        }


def _apply_metadata_filters(
    where_clauses: list[str],
    params: list,
    *,
    product_line: str | None = None,
    index_release_id: str | None = None,
    data_release_id: str | None = None,
    visibility_scope: str | None = None,
    entitlement_tier: str | None = None,
    status: str | None = None,
    quality_status: str | None = None,
) -> None:
    if index_release_id:
        where_clauses.append(f"ks.index_release_id = ${len(params)+1}")
        params.append(index_release_id)
    if data_release_id:
        where_clauses.append(f"COALESCE(ks.data_release_id, kd.data_release_id) = ${len(params)+1}")
        params.append(data_release_id)
    if product_line and product_line != "any":
        where_clauses.append(f"kd.product_line = ${len(params)+1}")
        params.append(product_line)
    if visibility_scope:
        where_clauses.append(f"kd.visibility_scope = ${len(params)+1}")
        params.append(visibility_scope)
    if entitlement_tier:
        where_clauses.append(f"kd.entitlement_tier = ${len(params)+1}")
        params.append(entitlement_tier)
    if status:
        where_clauses.append(f"kd.status = ${len(params)+1}")
        params.append(status)
    if quality_status:
        where_clauses.append(
            f"COALESCE(kd.quality_status, kd.quality_gate::text) = ${len(params)+1}"
        )
        params.append(quality_status)


# ── 嵌入查询向量生成 ──────────────────────────────────────────────────────────

class QueryEmbedder:
    """为查询文本生成嵌入向量（复用 pipelines/indexing/embedder 的逻辑）"""

    def __init__(self):
        self._provider = None

    def _get_provider(self):
        if self._provider is None:
            import sys
            sys.path.insert(0, str(os.path.dirname(__file__) + "/../../../"))
            try:
                from pipelines.indexing.embedder import EmbeddingProvider
                self._provider = EmbeddingProvider()
            except ImportError:
                self._provider = _FallbackEmbedder()
        return self._provider

    def embed(self, text: str) -> list[float]:
        return self._get_provider().embed_batch([text])[0]


class _FallbackEmbedder:
    """不可用时返回零向量（测试/骨架场景）"""
    def embed_batch(self, texts):
        return [[0.0] * 1536 for _ in texts]


_query_embedder = QueryEmbedder()


# ── 向量检索 ──────────────────────────────────────────────────────────────────

async def vector_search(
    conn,
    query: str,
    top_k: int,
    product_line: str | None = None,
    index_release_id: str | None = None,
    data_release_id: str | None = None,
    visibility_scope: str | None = None,
    entitlement_tier: str | None = None,
    status: str | None = None,
    quality_status: str | None = None,
) -> list[RetrievalResult]:
    """ANN 余弦相似度检索（pgvector）"""
    try:
        query_vec = _format_pgvector(_query_embedder.embed(query))
    except Exception as e:
        logger.warning(f"Embedding failed, skipping vector search: {e}")
        return []

    where_clauses = ["ks.embedding IS NOT NULL"]
    params: list = [query_vec]
    _apply_metadata_filters(
        where_clauses,
        params,
        product_line=product_line,
        index_release_id=index_release_id,
        data_release_id=data_release_id,
        visibility_scope=visibility_scope,
        entitlement_tier=entitlement_tier,
        status=status,
        quality_status=quality_status,
    )

    params.append(top_k)

    rows = await conn.fetch(
        f"""
        SELECT
            ks.section_id   AS chunk_id,
            COALESCE(ea.anchor_id, ks.section_id) AS evidence_id,
            ks.doc_id,
            ks.source_id,
            ks.content,
            ks.section_path,
            ks.section_type,
            ks.page_no,
            ks.bbox,
            ks.data_release_id,
            ks.index_release_id,
            kd.title,
            kd.source_url,
            kd.doc_version,
            1 - (ks.embedding <=> $1::vector) AS score
        FROM knowledge_section ks
        JOIN knowledge_doc kd ON ks.doc_id = kd.doc_id
        LEFT JOIN evidence_anchor ea ON ea.chunk_id = ks.section_id
        WHERE {" AND ".join(where_clauses)}
        ORDER BY ks.embedding <=> $1::vector
        LIMIT ${len(params)}
        """,
        *params,
    )

    return [
        RetrievalResult(
            chunk_id=r["chunk_id"],
            evidence_id=r["evidence_id"],
            doc_id=r["doc_id"],
            source_id=r["source_id"],
            content=r["content"],
            section_path=r["section_path"],
            section_type=r["section_type"],
            page_no=r["page_no"],
            title=r["title"],
            bbox=r["bbox"],
            source_url=r["source_url"],
            doc_version=r["doc_version"],
            data_release_id=r["data_release_id"],
            index_release_id=r["index_release_id"],
            vector_score=float(r["score"]),
        )
        for r in rows
    ]


# ── FTS 检索 ──────────────────────────────────────────────────────────────────

async def fts_search(
    conn,
    query: str,
    top_k: int,
    product_line: str | None = None,
    index_release_id: str | None = None,
    data_release_id: str | None = None,
    visibility_scope: str | None = None,
    entitlement_tier: str | None = None,
    status: str | None = None,
    quality_status: str | None = None,
) -> list[RetrievalResult]:
    """PostgreSQL 全文检索（tsvector + tsquery）"""
    fts_query = _build_fts_query(query)
    if not fts_query:
        return []
    where_clauses = [
        """(
            setweight(to_tsvector('english', COALESCE(kd.title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(ks.section_path, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(ks.content, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(ks.context_prefix, '')), 'B')
        ) @@ websearch_to_tsquery('english', $1)"""
    ]
    params: list = [fts_query]
    _apply_metadata_filters(
        where_clauses,
        params,
        product_line=product_line,
        index_release_id=index_release_id,
        data_release_id=data_release_id,
        visibility_scope=visibility_scope,
        entitlement_tier=entitlement_tier,
        status=status,
        quality_status=quality_status,
    )

    params.append(top_k)

    try:
        rows = await conn.fetch(
            f"""
            SELECT
                ks.section_id   AS chunk_id,
                COALESCE(ea.anchor_id, ks.section_id) AS evidence_id,
                ks.doc_id,
                ks.source_id,
                ks.content,
                ks.section_path,
                ks.section_type,
                ks.page_no,
                ks.bbox,
                ks.data_release_id,
                ks.index_release_id,
                kd.title,
                kd.source_url,
                kd.doc_version,
                ts_rank_cd(
                    setweight(to_tsvector('english', COALESCE(kd.title, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(ks.section_path, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(ks.content, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(ks.context_prefix, '')), 'B'),
                    websearch_to_tsquery('english', $1)
                ) AS score
            FROM knowledge_section ks
            JOIN knowledge_doc kd ON ks.doc_id = kd.doc_id
            LEFT JOIN evidence_anchor ea ON ea.chunk_id = ks.section_id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY score DESC
            LIMIT ${len(params)}
            """,
            *params,
        )
    except Exception as e:
        logger.warning(f"FTS search failed: {e}")
        return []

    return [
        RetrievalResult(
            chunk_id=r["chunk_id"],
            evidence_id=r["evidence_id"],
            doc_id=r["doc_id"],
            source_id=r["source_id"],
            content=r["content"],
            section_path=r["section_path"],
            section_type=r["section_type"],
            page_no=r["page_no"],
            title=r["title"],
            bbox=r["bbox"],
            source_url=r["source_url"],
            doc_version=r["doc_version"],
            data_release_id=r["data_release_id"],
            index_release_id=r["index_release_id"],
            fts_score=float(r["score"]),
        )
        for r in rows
    ]


def _build_fts_query(query: str) -> str:
    """Create a bounded OR query for recall; RRF/rerank remains the precision gate."""
    tokens = []
    seen = set()
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,63}", query):
        token = raw.lower()
        if token not in FTS_STOPWORDS and token not in seen:
            tokens.append(token)
            seen.add(token)
    return " OR ".join(tokens[:16])


# ── RRF 融合 ─────────────────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    vector_results: list[RetrievalResult],
    fts_results: list[RetrievalResult],
    k: int = 60,
) -> list[RetrievalResult]:
    """
    Reciprocal Rank Fusion：合并两路检索结果。
    RRF score = Σ 1/(k + rank_i)
    """
    scores: dict[str, float] = {}
    registry: dict[str, RetrievalResult] = {}

    for rank, result in enumerate(vector_results, 1):
        scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + 1.0 / (k + rank)
        registry[result.chunk_id] = result

    for rank, result in enumerate(fts_results, 1):
        scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + 1.0 / (k + rank)
        if result.chunk_id not in registry:
            registry[result.chunk_id] = result
        else:
            # 合并两路的分数
            existing = registry[result.chunk_id]
            existing.fts_score = result.fts_score

    # 按 RRF 分数排序
    merged = list(registry.values())
    for r in merged:
        r.rrf_score = scores[r.chunk_id]
    merged.sort(key=lambda x: x.rrf_score, reverse=True)
    return merged


# ── Governed remote rerank ────────────────────────────────────────────────────

class RemoteReranker:
    """SiliconFlow-compatible reranker with bounded inputs and RRF fallback."""

    @property
    def provider(self) -> str:
        if settings.rerank_provider == "disabled":
            return "disabled"
        return "siliconflow"

    @property
    def model(self) -> str:
        return settings.rerank_model

    async def rerank(
        self, query: str, results: list[RetrievalResult]
    ) -> tuple[list[RetrievalResult], str | None, float]:
        started = time.perf_counter()
        api_key = (
            settings.rerank_api_key
            or settings.openai_api_key
            or settings.siliconflow_api_key
            or os.environ.get("SILICONFLOW_API_KEY", "")
        )
        fallback_reason = None
        if settings.rerank_provider == "disabled":
            fallback_reason = "rerank_disabled"
        elif not api_key:
            fallback_reason = "rerank_not_configured"
        elif not results:
            fallback_reason = "no_candidates"
        else:
            try:
                request_body = {
                    "model": settings.rerank_model,
                    "query": query[:2048],
                    "documents": [item.content[:6000] for item in results],
                    "top_n": len(results),
                    "return_documents": False,
                }
                endpoint = settings.rerank_base_url.rstrip("/") + "/rerank"
                async with httpx.AsyncClient(timeout=settings.rerank_timeout_seconds) as client:
                    response = await client.post(
                        endpoint,
                        json=request_body,
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    response.raise_for_status()
                    payload = response.json()
                ranked = []
                seen = set()
                for item in payload.get("results", []):
                    index = item.get("index")
                    score = item.get("relevance_score")
                    if not isinstance(index, int) or not 0 <= index < len(results):
                        raise ValueError("invalid_rerank_index")
                    if not isinstance(score, (int, float)):
                        raise ValueError("invalid_rerank_score")
                    if index in seen:
                        raise ValueError("duplicate_rerank_index")
                    seen.add(index)
                    result = results[index]
                    result.rerank_score = float(score)
                    ranked.append(result)
                if len(ranked) != len(results):
                    raise ValueError("incomplete_rerank_results")
                results = ranked
            except Exception as exc:
                # Do not log request content or credentials.
                fallback_reason = f"remote_rerank_error:{type(exc).__name__}"
                logger.warning("Remote rerank failed; retaining RRF order (%s)", type(exc).__name__)

        latency_ms = (time.perf_counter() - started) * 1000
        for result in results:
            result.rerank_provider = self.provider
            result.rerank_model = self.model
            result.rerank_fallback_reason = fallback_reason
            result.rerank_latency_ms = latency_ms
        return results, fallback_reason, latency_ms


_reranker = RemoteReranker()


# ── 主检索接口 ────────────────────────────────────────────────────────────────

async def hybrid_retrieve(
    conn,
    query: str,
    top_k: int = 5,
    product_line: str | None = None,
    index_release_id: str = "index-v0.1.0",
    data_release_id: str | None = None,
    visibility_scope: str | None = None,
    entitlement_tier: str | None = None,
    status: str | None = None,
    quality_status: str | None = None,
    rerank: bool = True,
    min_score: float = 0.0,
    semantic_query: str | None = None,
    lexical_query: str | None = None,
    rerank_query: str | None = None,
) -> list[RetrievalResult]:
    """
    执行完整混合检索：vector + FTS → RRF → rerank → filter。

    `semantic_query` 只进入向量检索，`lexical_query` 只进入 FTS，原始
    `query` 默认用于 rerank。这样 Query Rewrite 可以扩展语义召回，同时
    保留错误码、型号等精确词，并让最终排序继续贴近用户原始意图。
    """
    vector_query = semantic_query or query
    keyword_query = lexical_query or query
    ranking_query = rerank_query or query

    async def run_vector_search():
        with traced_span(
            "rag.retrieve.vector",
            kind="RETRIEVER",
            attributes={"omni.retrieval.top_k": top_k * 2},
        ) as span:
            results = await vector_search(
                conn,
                vector_query,
                top_k * 2,
                product_line=product_line,
                index_release_id=index_release_id,
                data_release_id=data_release_id,
                visibility_scope=visibility_scope,
                entitlement_tier=entitlement_tier,
                status=status,
                quality_status=quality_status,
            )
            span.set_attribute("omni.retrieval.vector_hits", len(results))
            return results

    async def run_fts_search():
        with traced_span(
            "rag.retrieve.lexical",
            kind="RETRIEVER",
            attributes={"omni.retrieval.top_k": top_k * 2},
        ) as span:
            results = await fts_search(
                conn,
                keyword_query,
                top_k * 2,
                product_line=product_line,
                index_release_id=index_release_id,
                data_release_id=data_release_id,
                visibility_scope=visibility_scope,
                entitlement_tier=entitlement_tier,
                status=status,
                quality_status=quality_status,
            )
            span.set_attribute("omni.retrieval.lexical_hits", len(results))
            return results

    # asyncpg does not allow concurrent operations on one connection. The caller
    # provides one acquired connection, so run both legs sequentially; production
    # fan-out can acquire two connections before using asyncio.gather.
    vec_results = await run_vector_search()
    fts_results = await run_fts_search()

    # RRF 融合
    with traced_span(
        "rag.retrieve.rrf",
        kind="CHAIN",
        attributes={"omni.retrieval.rrf_k": 60},
    ) as fusion_span:
        merged = reciprocal_rank_fusion(vec_results, fts_results)
        fusion_span.set_attribute("omni.retrieval.fused_count", len(merged))

    # Remote cross-encoder 精排; retain deterministic RRF order on failure.
    if rerank and merged:
        before_count = len(merged[: top_k * 2])
        with traced_span(
            "rag.rerank.remote",
            kind="RERANKER",
            attributes={
                "reranker.provider": _reranker.provider,
                "reranker.model_name": _reranker.model,
                "omni.rerank.input_count": before_count,
            },
        ) as rerank_span:
            merged, fallback_reason, latency_ms = await _reranker.rerank(
                ranking_query, merged[: top_k * 2]
            )
            rerank_span.set_attribute("omni.rerank.output_count", len(merged))
            rerank_span.set_attribute("omni.rerank.dropped_count", before_count - len(merged))
            rerank_span.set_attribute("omni.rerank.fallback_reason", fallback_reason or "")
            rerank_span.set_attribute("omni.rerank.latency_ms", latency_ms)

    # 取 top_k + 最低分过滤
    results = merged[:top_k]
    if min_score > 0:
        results = [r for r in results if r.final_score >= min_score]

    return results
