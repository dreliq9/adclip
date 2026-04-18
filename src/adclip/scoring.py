"""Candidate scoring and ranking.

v0.1: deterministic heuristics. Future: LLM-as-judge (CLAUDE.md says local_review
for cheap first pass).
"""

from __future__ import annotations


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
    """Sort pool by score, descending.

    If per_bucket, pick top `n` per (format, angle) combo. Otherwise return
    top `n` overall.
    """
    scored = [(score_candidate(c), c) for c in pool]
    scored.sort(key=lambda sc: sc[0], reverse=True)

    if not per_bucket:
        return [c for _, c in scored[:n]]

    buckets: dict[tuple[str, str], list[dict]] = {}
    for s, c in scored:
        key = (c.get("format", ""), c.get("angle", ""))
        buckets.setdefault(key, []).append(c)

    out: list[dict] = []
    for cands in buckets.values():
        out.extend(cands[:n])
    return out
