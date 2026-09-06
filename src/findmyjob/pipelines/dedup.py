"""``dedup`` — link duplicate postings to one canonical job.

Three tiers, cheapest first:

1. **exact** — same ``(source_key, source_job_id)``; already enforced at fetch.
2. **canonical key** — same ``normalized_company | normalized_title``; the
   earliest job wins, later ones point at it via ``canonical_job_id``.
3. **semantic** — cosine similarity of an embedding of ``title + jd_text`` ≥
   threshold, compared only within the same company. Skipped entirely if the
   embedding model is unavailable.

No network, no LLM. Idempotent: a job already marked as a duplicate is left
alone; canonical jobs are re-checked (cheap).
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
from sqlmodel import Session, col, select

from findmyjob.models.enums import JobLifecycle
from findmyjob.models.job import Job, JobEmbedding
from findmyjob.normalize import (
    normalize_company_name,
    normalize_title,
    significant_title_words,
)
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.embeddings import (
    Embedder,
    cosine_matrix,
    from_bytes,
    get_embedder,
    to_bytes,
)

_SENTINEL = object()
_SIM_THRESHOLD = 0.92
_MAX_JOBS = 5000


#: below this Jaccard overlap of normalized title words, two postings from the
#: same employer are treated as different roles no matter how alike their text is.
_TITLE_OVERLAP_MIN = 0.5


def canonical_key(company_name: str, title: str) -> str:
    return f"{normalize_company_name(company_name)}|{normalize_title(title)}"


def titles_compatible(a: str, b: str) -> bool:
    """Could these two titles plausibly be the same role?

    Guards the semantic tier: one employer's postings share so much boilerplate
    that the embedding will merge "Account Executive" into "Enterprise AI
    Consultant". Job-type words are stripped first, so the cross-language and
    cross-source rewordings this tier exists for ("Werkstudent Analytics" vs
    "Working Student Analytics") still match.
    """
    ta, tb = significant_title_words(a), significant_title_words(b)
    if not ta or not tb:
        return True  # nothing to judge on - fall back to the embedding
    if ta <= tb or tb <= ta:
        return True  # one is a qualified variant of the other
    return len(ta & tb) / len(ta | tb) >= _TITLE_OVERLAP_MIN


class DedupPipeline(Pipeline):
    name: ClassVar[str] = "dedup"

    def __init__(self, embedder: Embedder | object | None = _SENTINEL) -> None:
        self._embedder = embedder

    def _resolve_embedder(self) -> Embedder | None:
        if self._embedder is _SENTINEL:
            return get_embedder()
        return self._embedder  # type: ignore[return-value]

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()

        with ctx.session() as session:
            jobs = list(
                session.exec(
                    select(Job)
                    .where(col(Job.lifecycle) == JobLifecycle.ACTIVE)
                    .order_by(col(Job.id))
                    .limit(_MAX_JOBS)
                ).all()
            )
            company_name = self._company_names(session, jobs)

            # ---- tier 2: canonical key ---------------------------------
            first_by_key: dict[str, int] = {}
            for job in jobs:
                if job.id is None or job.canonical_job_id is not None:
                    continue
                key = canonical_key(company_name.get(job.id, job.company_name_raw), job.title)
                owner = first_by_key.get(key)
                if owner is None:
                    first_by_key[key] = job.id
                elif owner != job.id:
                    job.canonical_job_id = owner
                    session.add(job)
                    res.bump("linked_by_key")
            session.flush()

            canonical_ids = [j.id for j in jobs if j.canonical_job_id is None and j.id is not None]

        # ---- tier 3: semantic ----------------------------------------
        embedder = self._resolve_embedder()
        if embedder is None:
            res.stats["semantic_skipped"] = 1
            res.finalize_status()
            return res

        self._semantic_pass(ctx, embedder, canonical_ids, res)
        res.finalize_status()
        return res

    # ---- helpers ----------------------------------------------------

    @staticmethod
    def _company_names(session: Session, jobs: list[Job]) -> dict[int, str]:
        from findmyjob.models.config import Company

        ids = {j.company_id for j in jobs if j.company_id is not None}
        if not ids:
            return {}
        rows = session.exec(select(Company).where(col(Company.id).in_(ids))).all()
        by_company = {c.id: c.name for c in rows}
        return {
            j.id: by_company.get(j.company_id, j.company_name_raw) for j in jobs if j.id is not None
        }

    def _semantic_pass(
        self,
        ctx: PipelineContext,
        embedder: Embedder,
        job_ids: list[int],
        res: PipelineResult,
    ) -> None:
        with ctx.session() as session:
            jobs = {
                j.id: j for j in session.exec(select(Job).where(col(Job.id).in_(job_ids))).all()
            }
            vectors: dict[int, np.ndarray] = {
                e.job_id: from_bytes(e.vector, e.dim)
                for e in session.exec(
                    select(JobEmbedding).where(col(JobEmbedding.job_id).in_(job_ids))
                ).all()
            }

            to_embed = [jid for jid in job_ids if jid not in vectors]
            if to_embed:
                texts = [
                    f"{jobs[jid].title}\n{(jobs[jid].jd_text or '')[:2000]}" for jid in to_embed
                ]
                try:
                    computed = embedder.embed(texts)
                except Exception as exc:  # embedding failed mid-run
                    res.add_error("embed", exc)
                    return
                for jid, vec in zip(to_embed, computed, strict=True):
                    vectors[jid] = np.asarray(vec, dtype=np.float32)
                    session.add(
                        JobEmbedding(
                            job_id=jid,
                            model_version=embedder.model_version,
                            dim=embedder.dim,
                            vector=to_bytes(vec),
                        )
                    )
                res.bump("embedded", len(to_embed))
            session.flush()

            # group canonical jobs by company, compare within group
            groups: dict[int | None, list[int]] = {}
            for jid in job_ids:
                groups.setdefault(jobs[jid].company_id, []).append(jid)

            for group_ids in groups.values():
                if len(group_ids) < 2:
                    continue
                matrix = np.stack([vectors[jid] for jid in group_ids])
                sims = cosine_matrix(matrix)
                for i in range(len(group_ids)):
                    for j in range(i):
                        if sims[i, j] < _SIM_THRESHOLD:
                            continue
                        dup, owner = jobs[group_ids[i]], jobs[group_ids[j]]
                        # Postings from one employer share so much boilerplate that
                        # the embedding alone will happily merge unrelated roles.
                        # The title is what actually distinguishes them.
                        if not titles_compatible(dup.title, owner.title):
                            res.bump("kept_title_differs")
                            continue
                        if dup.canonical_job_id is None:
                            dup.canonical_job_id = owner.canonical_job_id or owner.id
                            session.add(dup)
                            res.bump("linked_by_embedding")
                        break
