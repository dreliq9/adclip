"""Policy checks per profile. Hard rules become violations (drop variant);
soft rules become warnings (variant still usable).

The old Meta 20% text rule is NOT enforced — Meta removed it in 2020-2021.
Text density is a warning only, not a violation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from adclip.formats import AdFormatSpec


PolicyProfileName = Literal[
    "default", "crypto", "health", "alcohol", "financial_services"
]


@dataclass
class PolicyReport:
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Hard-rule phrase lists per profile (case-insensitive substring match).
_PROFILE_BLOCKED_PHRASES: dict[PolicyProfileName, list[str]] = {
    "default": [
        "guaranteed result", "risk free money",  # generic scam signals
    ],
    "crypto": [
        "guaranteed return", "guaranteed profit", "risk-free",
        "get rich quick", "100% safe", "no risk",
    ],
    "health": [
        "cures", "guaranteed cure", "miracle", "doctors hate",
        "fda approved",  # unless claim verified elsewhere
    ],
    "alcohol": [
        "healthy", "cures",  # no health claims on alcohol
    ],
    "financial_services": [
        "guaranteed approval", "no credit check",
    ],
}


def _char_limit_violations(
    headline: str, body: str, spec: AdFormatSpec
) -> list[str]:
    errs: list[str] = []
    if len(headline) > spec.headline_max > 0:
        errs.append(
            f"headline exceeds {spec.headline_max} chars "
            f"(got {len(headline)}) for format {spec.name}"
        )
    if len(body) > spec.body_max > 0:
        errs.append(
            f"body exceeds {spec.body_max} chars "
            f"(got {len(body)}) for format {spec.name}"
        )
    return errs


def _phrase_violations(
    text: str, phrases: list[str], kind: str
) -> list[str]:
    lower = text.lower()
    return [
        f"{kind} contains blocked phrase: {p!r}"
        for p in phrases if p.lower() in lower
    ]


def check_copy(
    *,
    headline: str,
    body: str,
    cta: str,
    format_spec: AdFormatSpec,
    profile: PolicyProfileName,
    must_include: list[str],
    must_avoid: list[str],
) -> PolicyReport:
    report = PolicyReport()
    joined = f"{headline}\n{body}\n{cta}"

    # Hard: char limits
    report.violations.extend(_char_limit_violations(headline, body, format_spec))

    # Hard: profile blocked phrases
    blocked = _PROFILE_BLOCKED_PHRASES.get(profile, [])
    report.violations.extend(_phrase_violations(joined, blocked, "copy"))

    # Hard: must-include missing
    for phrase in must_include:
        if phrase.lower() not in joined.lower():
            report.violations.append(f"missing required phrase: {phrase!r}")

    # Hard: must-avoid present
    report.violations.extend(_phrase_violations(joined, must_avoid, "copy"))

    # Soft: all-caps body (warning, not violation — Meta removed text density rule)
    letters = [c for c in body if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
        report.warnings.append("body is mostly caps — consider mixed case")

    # Soft: excessive punctuation
    if body.count("!") >= 3:
        report.warnings.append("body has 3+ exclamation marks — consider toning down")

    return report
