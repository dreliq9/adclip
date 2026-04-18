"""Candidate scoring and ranking.

v0.1: deterministic heuristics. Future: LLM-as-judge (CLAUDE.md says local_review
for cheap first pass).
"""

from __future__ import annotations

import re


def score_candidate(cand: dict) -> float:
    """Heuristic score in [0, 1].

    Rewards: enough length (not too short), balanced punctuation, specificity.
    Penalties: very short body, all-caps, repeated words.
    """
    headline = cand.get("headline", "")
    body = cand.get("body", "")

    score = 0.0

    # Headline length — favor meaty but not at the char limit
    h_len = len(headline)
    if h_len >= 15:
        score += 0.25
    elif h_len >= 8:
        score += 0.10

    # Body length — favor substantive
    b_len = len(body)
    if b_len >= 60:
        score += 0.35
    elif b_len >= 30:
        score += 0.20
    elif b_len >= 10:
        score += 0.05

    # Penalize all-caps body
    letters = [c for c in body if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
        score -= 0.15

    # Penalize obvious repetition in headline
    words = headline.lower().split()
    if len(words) >= 2 and len(set(words)) / len(words) < 0.6:
        score -= 0.15

    # Bonus: CTA phrase present in body? often redundant, slight penalty
    cta = cand.get("cta", "").lower()
    if cta and cta in body.lower():
        score -= 0.05

    # Specificity: digits, numerals often signal concrete claims
    if any(ch.isdigit() for ch in body):
        score += 0.10

    return max(0.0, min(1.0, score + 0.3))  # +0.3 baseline so decent copy ≈0.5+


def rank_pool(
    pool: list[dict], *, n: int, per_bucket: bool = False
) -> list[dict]:
    """Sort pool by score, descending. Attaches ``heuristic_score``.

    If per_bucket, pick top `n` per (format, angle) combo. Otherwise return
    top `n` overall.
    """
    attached = [{**c, "heuristic_score": score_candidate(c)} for c in pool]
    attached.sort(key=lambda c: c["heuristic_score"], reverse=True)

    if not per_bucket:
        return attached[:n]

    buckets: dict[tuple[str, str], list[dict]] = {}
    for c in attached:
        key = (c.get("format", ""), c.get("angle", ""))
        buckets.setdefault(key, []).append(c)

    out: list[dict] = []
    for cands in buckets.values():
        out.extend(cands[:n])
    return out


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def jaccard_similarity(a: dict, b: dict) -> float:
    """Jaccard similarity on headline+body tokens. 1.0 identical, 0.0 disjoint."""
    ta = _tokens(f"{a.get('headline', '')} {a.get('body', '')}")
    tb = _tokens(f"{b.get('headline', '')} {b.get('body', '')}")
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def ensure_variant_diversity(
    winners: list[dict],
    pool: list[dict],
    *,
    threshold: float = 0.6,
    max_swaps: int = 5,
) -> list[dict]:
    """Swap near-duplicate winners for dissimilar alternatives.

    Preserves format coverage: swap candidates must match the dropped winner's
    format. Uses judge_score if present, else heuristic score. Bounded by
    max_swaps to prevent oscillation on degenerate pools.
    """
    def _score(c: dict) -> float:
        if "judge_score" in c:
            return c["judge_score"]
        return score_candidate(c)

    out = list(winners)

    for _ in range(max_swaps):
        worst_pair = None
        worst_sim = threshold
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                s = jaccard_similarity(out[i], out[j])
                if s > worst_sim:
                    worst_sim = s
                    worst_pair = (i, j)
        if worst_pair is None:
            return out

        i, j = worst_pair
        drop_idx = i if _score(out[i]) < _score(out[j]) else j
        drop_format = out[drop_idx]["format"]

        remaining = [w for k, w in enumerate(out) if k != drop_idx]
        candidates = [
            c for c in pool
            if c["format"] == drop_format
            and c not in out
            and all(jaccard_similarity(c, r) <= threshold for r in remaining)
        ]
        if not candidates:
            return out
        out[drop_idx] = max(candidates, key=_score)

    return out


def ensure_format_coverage(
    winners: list[dict],
    survivors: list[dict],
    formats: list[str],
) -> list[dict]:
    """Swap lowest-scoring winner for the best survivor of each missing format.

    Only swaps when doing so won't orphan another format (i.e. the donor format
    has >1 winner). Uses `judge_score` if present, else the heuristic score.
    Returns the original list unchanged if coverage can't be improved.
    """
    if len(formats) > len(winners):
        return winners

    def _score(c: dict) -> float:
        if "judge_score" in c:
            return c["judge_score"]
        return score_candidate(c)

    out = list(winners)
    covered = {w["format"] for w in out}
    missing = [f for f in formats if f not in covered]
    for fmt in missing:
        candidates = [
            c for c in survivors
            if c["format"] == fmt and c not in out
        ]
        if not candidates:
            continue
        best = max(candidates, key=_score)

        fmt_counts: dict[str, int] = {}
        for w in out:
            fmt_counts[w["format"]] = fmt_counts.get(w["format"], 0) + 1

        drop_idx = None
        drop_score = float("inf")
        for i, w in enumerate(out):
            if fmt_counts[w["format"]] <= 1:
                continue
            s = _score(w)
            if s < drop_score:
                drop_idx = i
                drop_score = s
        if drop_idx is None:
            continue
        out[drop_idx] = best

    return out


async def judge_pool(
    pool: list[dict], *, brief, provider
) -> list[dict]:
    """Score every candidate and return the full list sorted by judge_score desc.

    Each candidate is augmented with judge_score, judge_rationale, judge_flags
    and heuristic_score (independent signal for cross-checking). Judge calls
    are dispatched concurrently via asyncio.gather.
    """
    import asyncio

    from adclip.judge import score_with_judge  # lazy import to avoid cycle

    judged = list(await asyncio.gather(
        *(score_with_judge(c, brief, provider=provider) for c in pool)
    ))
    judged = [{**c, "heuristic_score": score_candidate(c)} for c in judged]
    judged.sort(key=lambda c: c["judge_score"], reverse=True)
    return judged


async def rank_with_judge(
    pool: list[dict],
    *,
    brief,
    provider,
    n: int,
    per_bucket: bool = False,
) -> list[dict]:
    """Rank a pool using LLM-as-judge scores instead of the heuristic.

    Returns candidates augmented with judge_score, judge_rationale, judge_flags.
    """
    judged = await judge_pool(pool, brief=brief, provider=provider)

    if not per_bucket:
        return judged[:n]

    buckets: dict[tuple[str, str], list[dict]] = {}
    for c in judged:
        key = (c.get("format", ""), c.get("angle", ""))
        buckets.setdefault(key, []).append(c)

    out: list[dict] = []
    for cands in buckets.values():
        out.extend(cands[:n])
    return out
